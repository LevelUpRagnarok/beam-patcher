use crate::{Error, Result};
use flate2::read::ZlibDecoder;
use flate2::write::ZlibEncoder;
use std::io::{Read, Write};
use std::path::Path;

const THOR_MAGIC: &[u8; 24] = b"ASSF (C) 2007 Aeomin DEV";
// Conservative limits for parsing downloaded archives on 32- and 64-bit clients.
const MAX_THOR_FILES: usize = 100_000;
const MAX_THOR_TABLE_BYTES: usize = 16 * 1024 * 1024;
const MAX_THOR_ENTRY_BYTES: usize = 256 * 1024 * 1024;

fn read_u8<T: Read>(reader: &mut T) -> Result<u8> {
    let mut value = [0u8; 1];
    reader.read_exact(&mut value)?;
    Ok(value[0])
}

fn read_u16<T: Read>(reader: &mut T) -> Result<u16> {
    let mut value = [0u8; 2];
    reader.read_exact(&mut value)?;
    Ok(u16::from_le_bytes(value))
}

fn read_u32<T: Read>(reader: &mut T) -> Result<u32> {
    let mut value = [0u8; 4];
    reader.read_exact(&mut value)?;
    Ok(u32::from_le_bytes(value))
}

fn decode_zlib_limited(source: &[u8], limit: usize) -> Result<Vec<u8>> {
    let decoder = ZlibDecoder::new(source);
    let mut limited = decoder.take((limit as u64) + 1);
    let mut output = Vec::new();
    limited.read_to_end(&mut output)
        .map_err(|e| Error::Decompression(e.to_string()))?;
    if output.len() > limit {
        return Err(Error::InvalidFileEntry);
    }
    Ok(output)
}

/// THOR uses Windows paths, including on non-Windows CI runners.
pub fn validate_client_path(filename: &str) -> Result<()> {
    if filename.is_empty() || (filename.starts_with('/') || filename.starts_with('\\'))
        || filename.bytes().any(|b| b < 0x20 || b == b':' || b == b'|' ||
           b == b'<' || b == b'>' || b == b'"' || b == b'*' || b == b'?')
    {
        return Err(Error::InvalidFileEntry);
    }
    for segment in filename.split(['/', '\\']) {
        if segment.is_empty() || segment == "." || segment == ".."
            || (segment.ends_with(' ') || segment.ends_with('.'))
        {
            return Err(Error::InvalidFileEntry);
        }
        // Block Windows device paths even when the patch runs on Linux.
        let stem = segment.split('.').next().unwrap_or("").to_ascii_uppercase();
        if matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL")
            || ((stem.starts_with("COM") || stem.starts_with("LPT"))
                && stem.len() == 4 && matches!(stem.as_bytes()[3], b'1'..=b'9'))
        {
            return Err(Error::InvalidFileEntry);
        }
    }
    Ok(())
}

fn validate_target_grf(name: &str) -> Result<()> {
    validate_client_path(name)?;
    if (name.contains('/') || name.contains('\\')) || !name.to_ascii_lowercase().ends_with(".grf") {
        return Err(Error::InvalidFileEntry);
    }
    Ok(())
}


#[derive(Debug, Clone)]
pub enum ThorEntry {
    Add {
        filename: String,
        data: Vec<u8>,
    },
    Remove {
        filename: String,
    },
}

#[derive(Debug)]
pub struct Thor {
    pub entries: Vec<ThorEntry>,
    pub use_grf_merging: bool,
    pub target_grf_name: Option<String>,
}

impl Thor {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let data = std::fs::read(path)?;
        Self::from_bytes(&data)
    }
    
    pub fn from_bytes(data: &[u8]) -> Result<Self> {
        if !data.starts_with(THOR_MAGIC) {
            return Err(Error::InvalidThorHeader);
        }

        let mut cursor = std::io::Cursor::new(data);
        cursor.set_position(THOR_MAGIC.len() as u64);

        let use_grf_merging = match read_u8(&mut cursor)? {
            0 => false,
            1 => true,
            _ => return Err(Error::InvalidThorHeader),
        };
        let expected_files = read_u32(&mut cursor)? as usize;
        if expected_files > MAX_THOR_FILES {
            return Err(Error::InvalidThorHeader);
        }
        let mode = read_u16(&mut cursor)?;
        if mode != 0x30 && mode != 0x21 {
            return Err(Error::Custom(format!("Unsupported THOR mode: {mode:#x}")));
        }

        let target_len = read_u8(&mut cursor)? as usize;
        let mut target_bytes = vec![0u8; target_len];
        cursor.read_exact(&mut target_bytes)?;
        let target_grf_name = if target_bytes.is_empty() {
            None
        } else {
            let value = String::from_utf8(target_bytes)
                .map_err(|_| Error::InvalidThorHeader)?;
            validate_target_grf(&value)?;
            Some(value)
        };

        let compressed_len = read_u32(&mut cursor)? as usize;
        let file_table_offset = read_u32(&mut cursor)? as usize;
        let header_end = cursor.position() as usize;
        let table_end = file_table_offset.checked_add(compressed_len)
            .ok_or(Error::InvalidThorHeader)?;
        if file_table_offset < header_end || table_end > data.len() || compressed_len == 0 {
            return Err(Error::InvalidThorHeader);
        }

        // Bound the decompressed table to stop hostile THOR archives from consuming RAM.
        let table_data = decode_zlib_limited(
            &data[file_table_offset..table_end],
            MAX_THOR_TABLE_BYTES,
        )?;
        let mut table = std::io::Cursor::new(table_data);
        let mut entries = Vec::with_capacity(expected_files);
        let mut names = std::collections::HashSet::new();

        for _ in 0..expected_files {
            let name_len = read_u8(&mut table)? as usize;
            if name_len == 0 {
                return Err(Error::InvalidFileEntry);
            }
            let mut name_bytes = vec![0u8; name_len];
            table.read_exact(&mut name_bytes)?;
            // We do not silently replace invalid bytes: lossy conversion can change
            // the output path or make two distinct client filenames collide.
            let filename = String::from_utf8(name_bytes)
                .map_err(|_| Error::InvalidFileEntry)?;
            validate_client_path(&filename)?;
            if !names.insert(filename.replace('\\', "/").to_lowercase()) {
                return Err(Error::InvalidFileEntry);
            }
            let entry_type = read_u8(&mut table)?;
            match entry_type {
                0x00 => {
                    let start = read_u32(&mut table)? as usize;
                    let stored_len = read_u32(&mut table)? as usize;
                    let expanded_len = read_u32(&mut table)? as usize;
                    if expanded_len > MAX_THOR_ENTRY_BYTES || stored_len == 0 {
                        return Err(Error::InvalidFileEntry);
                    }
                    let end = start.checked_add(stored_len).ok_or(Error::InvalidFileEntry)?;
                    if start < header_end || end > file_table_offset {
                        return Err(Error::InvalidFileEntry);
                    }
                    let content = decode_zlib_limited(
                        &data[start..end],
                        expanded_len,
                    )?;
                    if content.len() != expanded_len {
                        return Err(Error::InvalidFileEntry);
                    }
                    entries.push(ThorEntry::Add { filename, data: content });
                }
                0x01 => entries.push(ThorEntry::Remove { filename }),
                _ => return Err(Error::InvalidFileEntry),
            }
        }

        if table.position() as usize != table.get_ref().len() {
            return Err(Error::InvalidFileEntry);
        }

        Ok(Self { entries, use_grf_merging, target_grf_name })
    }

    pub fn get_entries(&self) -> &[ThorEntry] {
        &self.entries
    }
    
    pub fn new() -> Self {
        Thor {
            entries: Vec::new(),
            use_grf_merging: false,
            target_grf_name: None,
        }
    }

    pub fn add_file(&mut self, filename: &str, data: &[u8]) {
        self.entries.push(ThorEntry::Add {
            filename: filename.to_string(),
            data: data.to_vec(),
        });
    }
    
    pub fn remove_file(&mut self, filename: &str) {
        self.entries.push(ThorEntry::Remove {
            filename: filename.to_string(),
        });
    }
    
    pub fn save<P: AsRef<Path>>(&self, path: P) -> Result<()> {
        use flate2::Compression as FlateCompression;
        
        let target_name = self.target_grf_name.as_deref().unwrap_or("");
        if !target_name.is_empty() {
            validate_target_grf(target_name)?;
        }
        if target_name.len() > u8::MAX as usize {
            return Err(Error::InvalidFileEntry);
        }
        let header_size = THOR_MAGIC.len() + 1 + 4 + 2 + 1 + target_name.len() + 4 + 4;
        let header_size = u32::try_from(header_size).map_err(|_| Error::InvalidThorHeader)?;

        let mut file_data = Vec::new();
        let mut table_data = Vec::new();
        
        for entry in &self.entries {
            match entry {
                ThorEntry::Add { filename, data } => {
                    validate_client_path(filename)?;
                    if filename.len() > 255 {
                        return Err(Error::Custom("Filename too long (max 255 bytes)".to_string()));
                    }
                    if data.len() > MAX_THOR_ENTRY_BYTES {
                        return Err(Error::InvalidFileEntry);
                    }

                    let mut encoder = ZlibEncoder::new(Vec::new(), FlateCompression::default());
                    encoder.write_all(data)?;
                    let compressed = encoder.finish()?;
                    
                    let offset = header_size.checked_add(
                        u32::try_from(file_data.len()).map_err(|_| Error::InvalidFileEntry)?
                    ).ok_or(Error::InvalidFileEntry)?;
                    let compressed_size = u32::try_from(compressed.len()).map_err(|_| Error::InvalidFileEntry)?;
                    let decompressed_size = u32::try_from(data.len()).map_err(|_| Error::InvalidFileEntry)?;
                    
                    file_data.write_all(&compressed)?;
                    
                    table_data.write_all(&[filename.len() as u8])?;
                    table_data.write_all(filename.as_bytes())?;
                    table_data.write_all(&[0x00])?;
                    table_data.write_all(&offset.to_le_bytes())?;
                    table_data.write_all(&compressed_size.to_le_bytes())?;
                    table_data.write_all(&decompressed_size.to_le_bytes())?;
                },
                ThorEntry::Remove { filename } => {
                    validate_client_path(filename)?;
                    if filename.len() > 255 {
                        return Err(Error::Custom("Filename too long (max 255 bytes)".to_string()));
                    }
                    
                    table_data.write_all(&[filename.len() as u8])?;
                    table_data.write_all(filename.as_bytes())?;
                    table_data.write_all(&[0x01])?;
                },
            }
        }
        
        let mut encoder = ZlibEncoder::new(Vec::new(), FlateCompression::default());
        encoder.write_all(&table_data)?;
        let compressed_table = encoder.finish()?;
        
        // All offsets include the optional target GRF field.
        let file_table_offset = header_size.checked_add(
            u32::try_from(file_data.len()).map_err(|_| Error::InvalidFileEntry)?
        ).ok_or(Error::InvalidFileEntry)?;
        let file_table_compressed_length =
            u32::try_from(compressed_table.len()).map_err(|_| Error::InvalidFileEntry)?;
        if self.entries.len() > MAX_THOR_FILES || table_data.len() > MAX_THOR_TABLE_BYTES {
            return Err(Error::InvalidFileEntry);
        }
        
        let mut file = std::fs::File::create(path)?;
        
        file.write_all(THOR_MAGIC)?;
        file.write_all(&[u8::from(self.use_grf_merging)])?;
        file.write_all(&(self.entries.len() as u32).to_le_bytes())?;
        file.write_all(&(0x30i16).to_le_bytes())?;
        file.write_all(&[target_name.len() as u8])?;
        file.write_all(target_name.as_bytes())?;
        file.write_all(&file_table_compressed_length.to_le_bytes())?;
        file.write_all(&file_table_offset.to_le_bytes())?;
        
        file.write_all(&file_data)?;
        file.write_all(&compressed_table)?;

        Ok(())
    }
}

impl Default for Thor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;



    #[test]
    fn roundtrips_loose_client_thor_without_grf_target() {
        let root = std::env::temp_dir().join(format!(
            "beam-thor-loose-{}-{}.thor", std::process::id(), 719
        ));
        let mut archive = Thor::new();
        archive.add_file("SystemEN/LuaFiles514/itemInfo.lua", b"translation");
        archive.remove_file("data/obsolete.txt");
        archive.save(&root).expect("write THOR");
        let result = Thor::open(&root).expect("read THOR");
        let _ = std::fs::remove_file(&root);
        assert!(!result.use_grf_merging);
        assert!(result.target_grf_name.is_none());
        assert_eq!(result.entries.len(), 2);
        match &result.entries[0] {
            ThorEntry::Add { filename, data } => {
                assert_eq!(filename, "SystemEN/LuaFiles514/itemInfo.lua");
                assert_eq!(data, b"translation");
            }
            _ => panic!("expected add"),
        }
    }

    #[test]
    fn roundtrips_grf_merging_and_target_filename() {
        let root = std::env::temp_dir().join(format!(
            "beam-thor-grf-{}-{}.thor", std::process::id(), 721
        ));
        let mut archive = Thor::new();
        archive.use_grf_merging = true;
        archive.target_grf_name = Some("ragnardata.grf".to_owned());
        archive.add_file("data/sprite/test.spr", b"dummy sprite");
        archive.save(&root).expect("write GRF THOR");
        let result = Thor::open(&root).expect("read GRF THOR");
        let _ = std::fs::remove_file(&root);
        assert!(result.use_grf_merging);
        assert_eq!(result.target_grf_name.as_deref(), Some("ragnardata.grf"));
        assert_eq!(result.entries.len(), 1);
    }

    #[test]
    fn rejects_corrupt_compressed_entry_instead_of_emitting_empty_file() {
        let mut raw = build_small_thor();
        // The table entry holds compressed_data offset starting at byte 40.
        raw[40] ^= 0xFF;
        assert!(Thor::from_bytes(&raw).is_err());
    }

    #[test]
    fn rejects_size_disagreement_and_truncated_archive() {
        let mut raw = build_small_thor();
        raw.pop(); // Truncated compressed table
        assert!(Thor::from_bytes(&raw).is_err());
        // File expansion size test is covered by strict decoder length guard.
    }

    #[test]
    fn rejects_unsafe_client_file_paths() {
        for bad in [
            "../SystemEN/foo", "..\\evil.txt", "C:\\Windows\\evil.dll",
            "/etc/passwd", "\\\\evilhost\\share", "data//nested.txt",
            "data/./foo", "data/AUX.txt", "data/test:ads", "data/NUL",
        ] {
            assert!(validate_client_path(bad).is_err(), "{bad}");
        }
        for good in ["SystemEN/LuaFiles514/itemInfo.lua", "data\\sprite\\sample.spr"] {
            assert!(validate_client_path(good).is_ok(), "{good}");
        }
    }

    fn build_small_thor() -> Vec<u8> {
        // Multiple tests call this helper in parallel: a PID-only fixed
        // filename lets one test remove another test's THOR fixture.
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("system time")
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "beam-thor-test-{}-{stamp}.thor", std::process::id()
        ));
        let mut archive = Thor::new();
        archive.add_file("data/example.txt", b"actual payload");
        archive.save(&path).unwrap();
        let bytes = std::fs::read(&path).unwrap();
        let _ = std::fs::remove_file(path);
        bytes
    }

    #[test]
    fn rejects_truncated_header_without_panic() {
        // Shorter than the 24-byte magic.
        assert!(Thor::from_bytes(b"ASSF").is_err());
        // 24 bytes of magic but missing every following field.
        assert!(Thor::from_bytes(THOR_MAGIC).is_err());
    }

    #[test]
    fn rejects_out_of_bounds_file_table_offset() {
        // Craft a THOR with a sane magic but a file_table_offset past EOF.
        // Layout up to file_table_offset (using mode 0x30, target_grf_len=0):
        //   [24 magic][1 use_grf][4 num_files][2 mode][1 tg_len]
        //   [4 file_table_compressed_len][4 file_table_offset]
        let mut data = Vec::new();
        data.extend_from_slice(THOR_MAGIC);
        data.push(0x00);                                    // use_grf_merging
        data.extend_from_slice(&0u32.to_le_bytes());        // num_files
        data.extend_from_slice(&0x30i16.to_le_bytes());     // mode
        data.push(0x00);                                    // target_grf_len
        data.extend_from_slice(&16u32.to_le_bytes());       // compressed_len
        // Offset is past end of file → must be rejected, not panic.
        data.extend_from_slice(&0xFFFF_FFFFu32.to_le_bytes());

        match Thor::from_bytes(&data) {
            Err(Error::InvalidThorHeader) => {}
            other => panic!("expected InvalidThorHeader, got {:?}", other),
        }
    }
}
