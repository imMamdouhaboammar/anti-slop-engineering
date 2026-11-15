pub fn is_doc_file(path: &str) -> bool {
    path.ends_with(".md")
        || path.ends_with(".markdown")
        || path.ends_with(".txt")
        || path.ends_with(".rst")
        || path.contains("/docs/")
        || path.starts_with("docs/")
}

pub fn is_test_file(path: &str) -> bool {
    path.contains("/tests/")
        || path.starts_with("tests/")
        || path.contains("_test.")
        || path.contains(".test.")
        || path.contains(".spec.")
        || path.contains("/test_")
        || path.starts_with("test_")
}

/// Unquote and unescape a git diff path, resolving C-style octal escape sequences
pub fn clean_git_path(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed == "/dev/null" {
        return String::new();
    }

    let unquoted = if trimmed.starts_with('"') && trimmed.ends_with('"') && trimmed.len() >= 2 {
        unescape_git_c_string(&trimmed[1..trimmed.len() - 1])
    } else {
        trimmed.to_string()
    };

    let stripped = if let Some(rest) = unquoted.strip_prefix("b/") {
        rest
    } else if let Some(rest) = unquoted.strip_prefix("a/") {
        rest
    } else {
        &unquoted
    };

    normalize_path(stripped)
}

fn parse_octal_byte(chars: &[char], start: usize) -> (u8, usize) {
    let mut val = (chars[start] as u32) - ('0' as u32);
    let mut idx = start;
    let mut count = 1;
    while count < 3 && idx + 1 < chars.len() && chars[idx + 1] >= '0' && chars[idx + 1] <= '7' {
        idx += 1;
        count += 1;
        val = val * 8 + ((chars[idx] as u32) - ('0' as u32));
    }
    (val as u8, idx)
}

fn decode_escape_char(c: char) -> Option<u8> {
    match c {
        'n' => Some(b'\n'),
        'r' => Some(b'\r'),
        't' => Some(b'\t'),
        'b' => Some(b'\x08'),
        'f' => Some(b'\x0c'),
        'a' => Some(b'\x07'),
        'v' => Some(b'\x0b'),
        '\\' => Some(b'\\'),
        '"' => Some(b'"'),
        _ => None,
    }
}

/// Unescape Git's C-style quoted string (octal escapes \303\251 and standard \", \\, \n, \t, etc.)
fn unescape_git_c_string(s: &str) -> String {
    let mut bytes: Vec<u8> = Vec::with_capacity(s.len());
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;

    while i < chars.len() {
        if chars[i] != '\\' || i + 1 >= chars.len() {
            let mut buf = [0u8; 4];
            bytes.extend_from_slice(chars[i].encode_utf8(&mut buf).as_bytes());
            i += 1;
            continue;
        }

        i += 1;
        let c = chars[i];
        if matches!(c, '0'..='7') {
            let (b, next_idx) = parse_octal_byte(&chars, i);
            bytes.push(b);
            i = next_idx + 1;
            continue;
        }

        if let Some(b) = decode_escape_char(c) {
            bytes.push(b);
        } else {
            let mut buf = [0u8; 4];
            bytes.extend_from_slice(c.encode_utf8(&mut buf).as_bytes());
        }
        i += 1;
    }

    String::from_utf8(bytes).unwrap_or_else(|e| String::from_utf8_lossy(e.as_bytes()).into_owned())
}

/// Normalize path components, resolving "." and ".." and stripping leading slashes
pub fn normalize_path(path: &str) -> String {
    let trimmed = path.trim().replace('\\', "/");
    let mut parts: Vec<&str> = Vec::new();

    for seg in trimmed.split('/') {
        if seg.is_empty() || seg == "." {
            continue;
        }
        if seg != ".." {
            parts.push(seg);
            continue;
        }
        if matches!(parts.last(), Some(&last) if last != "..") {
            parts.pop();
        } else {
            parts.push("..");
        }
    }

    parts.join("/")
}

fn extract_binary_file(line: &str) -> Option<String> {
    let rest = line.strip_prefix("Binary files ")?;
    let and_idx = rest.find(" and ")?;
    let target_part = &rest[and_idx + 5..];
    let differ_idx = target_part.rfind(" differ")?;
    let cleaned = clean_git_path(&target_part[..differ_idx]);
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned)
    }
}

fn extract_target_part(trimmed: &str) -> &str {
    if let Some(last_quote_start) = trimmed.rfind(" \"b/") {
        &trimmed[last_quote_start + 1..]
    } else if let Some(last_b) = trimmed.rfind(" b/") {
        &trimmed[last_b + 1..]
    } else {
        trimmed
    }
}

pub fn extract_target_file(line: &str) -> Option<String> {
    if let Some(rest) = line.strip_prefix("diff --git ") {
        let cleaned = clean_git_path(extract_target_part(rest.trim()));
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    if let Some(rest) = line.strip_prefix("+++ ") {
        let cleaned = clean_git_path(rest);
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    if let Some(rest) = line.strip_prefix("rename to ") {
        let cleaned = clean_git_path(rest);
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    if let Some(rest) = line.strip_prefix("copy to ") {
        let cleaned = clean_git_path(rest);
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    if line.starts_with("Binary files ") {
        return extract_binary_file(line);
    }
    None
}

fn extract_source_part(trimmed: &str) -> &str {
    if trimmed.starts_with('"') {
        if let Some(end_quote) = trimmed[1..].find('"') {
            &trimmed[..end_quote + 2]
        } else {
            trimmed
        }
    } else if let Some(space_idx) = trimmed.find(' ') {
        &trimmed[..space_idx]
    } else {
        trimmed
    }
}

pub fn extract_source_file(line: &str) -> Option<String> {
    if let Some(rest) = line.strip_prefix("--- ") {
        let cleaned = clean_git_path(rest);
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    if let Some(rest) = line.strip_prefix("rename from ") {
        let cleaned = clean_git_path(rest);
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    if let Some(rest) = line.strip_prefix("copy from ") {
        let cleaned = clean_git_path(rest);
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    if let Some(rest) = line.strip_prefix("diff --git ") {
        let cleaned = clean_git_path(extract_source_part(rest.trim()));
        if !cleaned.is_empty() {
            return Some(cleaned);
        }
    }
    None
}
