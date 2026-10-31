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
