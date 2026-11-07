//! Vieux parler et gothique, par Vetuste Scripteur (https://github.com/XNinety9/vetuste_scripteur),
//! appelé en ligne de commande, comme Barnum.
//!
//! Commande : `$PRINTR_VETUSTE` (par exemple `python3 /opt/vetuste/vetuste-scripteur.pyz`), sinon
//! `vetuste-scripteur`.

use std::io::Read;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use anyhow::{Context, Result, anyhow, bail};

/// Sur un Pi Zero, Python démarre lentement : bien plus de marge que pour un appel courant.
const TIMEOUT: Duration = Duration::from_secs(30);

/// Commande de Vetuste Scripteur, découpée en programme et arguments.
pub fn command() -> Vec<String> {
    std::env::var("PRINTR_VETUSTE")
        .ok()
        .filter(|c| !c.trim().is_empty())
        .unwrap_or_else(|| "vetuste-scripteur".to_owned())
        .split_whitespace()
        .map(str::to_owned)
        .collect()
}

/// Lance la gravure : `text` transmogrifié, en gothique, dans un PNG noir et blanc de `width` pixels.
/// Avec une `seed`, le même texte redonne la même image. `level` va de 0 (vocabulaire seul) à 3
/// (grimoire illisible) ; 2 par défaut.
pub fn engrave(text: &str, width: u32, seed: Option<u64>, level: Option<u8>) -> Result<Vec<u8>> {
    let command = command();
    let (program, base) = command.split_first().context("commande Vetuste Scripteur vide")?;
    let mut cmd = Command::new(program);
    cmd.args(base).arg("--png").arg(format!("--largeur={width}"));
    if let Some(seed) = seed {
        cmd.arg(format!("--seed={seed}"));
    }
    if let Some(level) = level {
        cmd.arg(format!("--niveau={level}"));
    }
    // Le texte après `--` : venu de l'appli, il ne peut jamais être pris pour une option.
    cmd.arg("--").arg(text);

    let mut child = cmd
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| anyhow!("impossible de lancer Vetuste Scripteur (« {program} ») : {e}"))?;

    // Lus dans des fils à part : une image dépasse vite la capacité du tuyau, et le programme
    // resterait bloqué en écriture si on attendait d'abord qu'il se termine.
    let mut stdout = child.stdout.take().context("sortie indisponible")?;
    let mut stderr = child.stderr.take().context("erreurs indisponibles")?;
    let out = thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout.read_to_end(&mut bytes).map(|_| bytes)
    });
    let err = thread::spawn(move || {
        let mut bytes = Vec::new();
        let _ = stderr.read_to_end(&mut bytes);
        bytes
    });

    let start = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break status;
        }
        if start.elapsed() > TIMEOUT {
            let _ = child.kill();
            let _ = child.wait();
            bail!("Vetuste Scripteur ne répond pas");
        }
        thread::sleep(Duration::from_millis(20));
    };

    let bytes = out.join().map_err(|_| anyhow!("lecture interrompue"))??;
    let message = err.join().map_err(|_| anyhow!("lecture interrompue"))?;
    if !status.success() {
        bail!("Vetuste Scripteur a échoué : {}", String::from_utf8_lossy(&message).trim());
    }
    if !bytes.starts_with(b"\x89PNG") {
        bail!("Vetuste Scripteur n'a pas renvoyé d'image");
    }
    Ok(bytes)
}
