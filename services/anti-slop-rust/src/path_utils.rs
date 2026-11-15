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

#[derive(Default)]
pub(crate) struct DiffPaths {
    source: Option<String>,
    target: Option<String>,
}

pub(crate) fn is_git_file_header(line: &str) -> bool {
    line == "diff --git" || line.starts_with("diff --git ")
}

impl DiffPaths {
    pub(crate) fn update(&mut self, line: &str) {
        if is_git_file_header(line) {
            (self.source, self.target) =
                match line.strip_prefix("diff --git ").and_then(parse_file_header) {
                    Some((source, target)) => (Some(source), Some(target)),
                    None => (None, None),
                };
        } else if let Some(operand) = line.strip_prefix("--- ") {
            self.source = parse_path(operand.strip_suffix('\t').unwrap_or(operand), "a/");
        } else if let Some(operand) = line.strip_prefix("+++ ") {
            self.target = if operand == "/dev/null" {
                self.source.clone()
            } else {
                parse_path(operand.strip_suffix('\t').unwrap_or(operand), "b/")
            };
        } else if let Some(operand) = line
            .strip_prefix("rename from ")
            .or_else(|| line.strip_prefix("copy from "))
        {
            self.source = parse_path(operand, "");
        } else if let Some(operand) = line
            .strip_prefix("rename to ")
            .or_else(|| line.strip_prefix("copy to "))
        {
            self.target = parse_path(operand, "");
        }
    }

    pub(crate) fn source(&self) -> &str {
        self.source.as_deref().unwrap_or_default()
    }

    pub(crate) fn target(&self) -> &str {
        self.target.as_deref().unwrap_or_default()
    }
}

fn parse_file_header(header: &str) -> Option<(String, String)> {
    let pair = if let Some(quoted) = header.strip_prefix('"') {
        let mut chars = quoted.char_indices();
        loop {
            match chars.next()? {
                (_, '\\') => {
                    chars.next()?;
                }
                (index, '"') => break header.split_at(index + 2),
                _ => {}
            }
        }
    } else if let Some((source, _)) = header.split_once(" \"b/") {
        (source, &header[source.len()..])
    } else {
        // Git does not quote spaces. Prioritize equal operands for edits to
        // the same path, and leave ambiguous renames to their metadata.
        let middle = header.len() / 2;
        if let (Some(source), Some(target)) = (header.get(..middle), header.get(middle + 1..)) {
            if header.as_bytes().get(middle) == Some(&b' ')
                && source.strip_prefix("a/") == target.strip_prefix("b/")
            {
                return Some((parse_path(source, "a/")?, parse_path(target, "b/")?));
            }
        }
        let mut separators = header.match_indices(" b/");
        let (offset, _) = separators.next()?;
        if separators.next().is_some() {
            return None;
        }
        header.split_at(offset)
    };
    Some((
        parse_path(pair.0, "a/")?,
        parse_path(pair.1.strip_prefix(' ')?, "b/")?,
    ))
}

fn parse_path(raw: &str, prefix: &str) -> Option<String> {
    let path = if let Some(quoted) = raw.strip_prefix('"') {
        unescape_git_path(quoted.strip_suffix('"')?)?
    } else {
        if raw.contains(['"', '\\', '\t']) {
            return None;
        }
        raw.to_owned()
    };
    let path = path.strip_prefix(prefix)?;
    (!path.is_empty() && !path.contains('\0')).then(|| path.to_owned())
}

fn unescape_git_path(quoted: &str) -> Option<String> {
    let mut bytes = Vec::with_capacity(quoted.len());
    let mut input = quoted.bytes();
    while let Some(byte) = input.next() {
        let decoded = match byte {
            b'"' => return None,
            b'\\' => match input.next()? {
                b'a' => 7,
                b'b' => 8,
                b't' => b'\t',
                b'n' => b'\n',
                b'v' => 11,
                b'f' => 12,
                b'r' => b'\r',
                byte @ (b'\\' | b'"') => byte,
                first @ b'0'..=b'3' => {
                    let second = input.next()?.checked_sub(b'0').filter(|n| *n < 8)?;
                    let third = input.next()?.checked_sub(b'0').filter(|n| *n < 8)?;
                    (first - b'0') * 64 + second * 8 + third
                }
                _ => return None,
            },
            _ => byte,
        };
        bytes.push(decoded);
    }
    String::from_utf8(bytes).ok()
}

pub(crate) fn is_relative_git_path(path: &str) -> bool {
    let driven = path.as_bytes().get(1) == Some(&b':') && path.as_bytes()[0].is_ascii_alphabetic();
    !driven && !path.contains('\0') && path.split('/').all(|part| !matches!(part, "" | "." | ".."))
}

pub(crate) fn scope_matches(path: &str, scope: &str) -> bool {
    let prefix = scope.strip_suffix('/').unwrap_or(scope);
    is_relative_git_path(prefix)
        && ((path == prefix && !scope.ends_with('/'))
            || path
                .strip_prefix(prefix)
                .is_some_and(|rest| rest.starts_with('/')))
}
