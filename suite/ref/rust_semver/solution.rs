#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version { pub major: u64, pub minor: u64, pub patch: u64 }
fn num(p: &str) -> Result<u64, String> {
    if p.is_empty() || !p.bytes().all(|b| b.is_ascii_digit()) || (p.len() > 1 && p.starts_with('0')) { return Err(format!("bad part {p}")); }
    p.parse().map_err(|_| "overflow".into())
}
pub fn parse(s: &str) -> Result<Version, String> {
    let s = s.trim(); let s = s.strip_prefix('v').unwrap_or(s);
    let p: Vec<&str> = s.split('.').collect();
    if p.len() != 3 { return Err("need 3 parts".into()); }
    Ok(Version { major: num(p[0])?, minor: num(p[1])?, patch: num(p[2])? })
}
fn one(v: &Version, c: &str) -> Result<bool, String> {
    let c = c.trim();
    for op in [">=", "<=", ">", "<", "=", "^", "~"] {
        if let Some(rest) = c.strip_prefix(op) {
            let r = parse(rest)?;
            return Ok(match op {
                ">=" => *v >= r, "<=" => *v <= r, ">" => *v > r, "<" => *v < r, "=" => *v == r,
                "~" => *v >= r && *v < Version { major: r.major, minor: r.minor + 1, patch: 0 },
                _ => { let up = if r.major > 0 { Version { major: r.major + 1, minor: 0, patch: 0 } } else if r.minor > 0 { Version { major: 0, minor: r.minor + 1, patch: 0 } } else { Version { major: 0, minor: 0, patch: r.patch + 1 } }; *v >= r && *v < up }
            });
        }
    }
    Ok(*v == parse(c)?)
}
pub fn satisfies(v: &Version, req: &str) -> Result<bool, String> {
    if req.trim().is_empty() { return Err("empty".into()); }
    let mut ok = true;
    for c in req.split(',') { ok &= one(v, c)?; }
    Ok(ok)
}
