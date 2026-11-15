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

pub(crate) fn is_relative_git_path(path: &str) -> bool {
    let windows_drive =
        path.as_bytes().get(1) == Some(&b':') && path.as_bytes()[0].is_ascii_alphabetic();
    !windows_drive
        && !path.contains(['\\', '\0'])
        && path.split('/').all(|part| !matches!(part, "" | "." | ".."))
}

pub(crate) fn path_matches_scope(path: &str, scope: &str) -> bool {
    let prefix = scope.strip_suffix('/').unwrap_or(scope);
    is_relative_git_path(prefix)
        && ((prefix == path && !scope.ends_with('/'))
            || path
                .strip_prefix(prefix)
                .is_some_and(|rest| rest.starts_with('/')))
}
