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
