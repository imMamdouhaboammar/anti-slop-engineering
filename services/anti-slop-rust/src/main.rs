use anti_slop_rust::ladder_auditor::LadderAuditor;
use anti_slop_rust::model::AuditReport;
use anti_slop_rust::server;
use anti_slop_rust::shit_interceptor::ShitInterceptor;
use clap::{Parser, Subcommand};
use std::fs;
use std::io::{self, Read};
use std::process::Command;

#[derive(Parser)]
#[command(name = "anti-slop-rust")]
#[command(about = "High-performance Anti-Slop & Clean Architecture Triage Engine", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Inspect a diff or git change for Scope creep, Hypothetical hardening, Intent violation, Task thrashing (SHIT)
    ShitCheck {
        /// Path to diff file (or omit to read from stdin)
        #[arg(short, long)]
        diff: Option<String>,

        /// Allowed file prefixes to check against scope creep (comma-separated)
        #[arg(short, long)]
        allowed: Option<String>,

        /// Flag if the current agent intent is strictly read-only / review
        #[arg(long)]
        read_only: bool,

        /// Output format: text or json
        #[arg(short, long, default_value = "text")]
        format: String,
    },

    /// Audit code additions for Senior Dev Ladder & Boring Built-in compliance
    LadderAudit {
        /// Target source files to inspect (directories are not supported)
        #[arg(required = true)]
        paths: Vec<String>,

        /// Output format: text or json
        #[arg(short, long, default_value = "text")]
        format: String,
    },

    /// Run full native triage against active git diff
    Triage {
        /// Git base reference (default: HEAD)
        #[arg(short, long, default_value = "HEAD")]
        base: String,

        /// Flag if the current turn is read-only
        #[arg(long)]
        read_only: bool,

        /// Output format: text or json
        #[arg(short, long, default_value = "text")]
        format: String,
    },

    /// Start the background HTTP microservice daemon
    Serve {
        /// Port to bind the HTTP service on
        #[arg(short, long, default_value_t = 9091)]
        port: u16,
    },
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    match cli.command {
        Commands::ShitCheck {
            diff,
            allowed,
            read_only,
            format,
        } => run_shit_check(diff, allowed, read_only, &format)?,

        Commands::LadderAudit { paths, format } => run_ladder_audit(paths, &format)?,

        Commands::Triage {
            base,
            read_only,
            format,
        } => run_triage(&base, read_only, &format)?,

        Commands::Serve { port } => {
            server::run_server(port).await?;
        }
    }

    Ok(())
}

fn run_shit_check(
    diff: Option<String>,
    allowed: Option<String>,
    read_only: bool,
    format: &str,
) -> io::Result<()> {
    let diff_content = match diff {
        Some(path) => fs::read_to_string(path)?,
        None => {
            let mut buffer = String::new();
            io::stdin().read_to_string(&mut buffer)?;
            buffer
        }
    };

    let allowed_vec: Option<Vec<&str>> = allowed
        .as_ref()
        .map(|s| s.split(',').map(|item| item.trim()).collect());

    let interceptor = ShitInterceptor::new();
    let findings = interceptor.audit_diff(&diff_content, allowed_vec.as_deref(), read_only);

    let report = AuditReport::new("anti-slop-rust-sts", findings);
    finish_with_report(&report, format);
    Ok(())
}

fn run_ladder_audit(paths: Vec<String>, format: &str) -> io::Result<()> {
    let auditor = LadderAuditor::new();
    let mut all_findings = Vec::new();

    for path in paths {
        let content = fs::read_to_string(&path).map_err(|e| {
            io::Error::new(e.kind(), format!("Cannot read '{}': {}", path, e))
        })?;
        let mut findings = auditor.audit_code(&path, &content);
        all_findings.append(&mut findings);
    }

    let report = AuditReport::new("anti-slop-rust-ladder", all_findings);
    finish_with_report(&report, format);
    Ok(())
}

fn run_triage(base: &str, read_only: bool, format: &str) -> io::Result<()> {
    let output = Command::new("git").args(["diff", base, "--"]).output()?;
    if !output.status.success() {
        return Err(io::Error::new(
            io::ErrorKind::Other,
            format!("git diff {} failed: {}", base, String::from_utf8_lossy(&output.stderr)),
        ));
    }
    let diff_content = String::from_utf8_lossy(&output.stdout).to_string();

    let report = anti_slop_rust::triage_diff(&diff_content, None, read_only);
    finish_with_report(&report, format);
    Ok(())
}

fn finish_with_report(report: &AuditReport, format: &str) {
    output_report(report, format);
    if report.summary.blockers > 0 {
        std::process::exit(1);
    }
}

fn output_report(report: &AuditReport, format: &str) {
    if format == "json" {
        if let Ok(json) = serde_json::to_string_pretty(report) {
            println!("{}", json);
        }
    } else {
        println!(
            "== Anti-Slop Rust Engine [{}] Status: {} ==",
            report.engine, report.summary.status
        );
        println!(
            "Total Findings: {} (Blockers: {}, Needs Review: {}, Info: {})",
            report.summary.total_findings,
            report.summary.blockers,
            report.summary.reviews,
            report.summary.infos
        );

        if !report.findings.is_empty() {
            println!("------------------------------------------------------------");
            for f in &report.findings {
                println!(
                    "[{:?}] {}:{}: [{}] {}",
                    f.severity, f.file, f.line, f.code, f.message
                );
                println!("  Suggestion: {}", f.suggestion);
            }
            println!("------------------------------------------------------------");
        }
    }
}
