use axum::{
    extract::Json,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;

use crate::model::AuditReport;
use crate::{LADDER_AUDITOR, SHIT_INTERCEPTOR};

#[derive(Serialize)]
struct HealthResponse {
    status: &'static str,
    service: &'static str,
    version: &'static str,
}

#[derive(Deserialize)]
pub struct ShitCheckRequest {
    pub diff: String,
    pub allowed_files: Option<Vec<String>>,
    #[serde(default)]
    pub read_only: bool,
}

#[derive(Deserialize)]
pub struct LadderAuditRequest {
    pub file: String,
    pub content: String,
}

#[derive(Deserialize)]
pub struct TriageRequest {
    pub diff: String,
    pub allowed_files: Option<Vec<String>>,
    #[serde(default)]
    pub read_only: bool,
}

async fn health_handler() -> impl IntoResponse {
    Json(HealthResponse {
        status: "ok",
        service: "anti-slop-rust",
        version: env!("CARGO_PKG_VERSION"),
    })
}

fn map_allowed_refs(allowed: Option<&Vec<String>>) -> Option<Vec<&str>> {
    allowed.map(|list| list.iter().map(String::as_str).collect())
}

async fn shit_check_handler(Json(payload): Json<ShitCheckRequest>) -> impl IntoResponse {
    let allowed_refs = map_allowed_refs(payload.allowed_files.as_ref());

    let findings = SHIT_INTERCEPTOR.audit_diff(
        &payload.diff,
        allowed_refs.as_deref(),
        payload.read_only,
    );

    let report = AuditReport::new("anti-slop-rust-sts", findings);
    (StatusCode::OK, Json(report))
}

async fn ladder_audit_handler(Json(payload): Json<LadderAuditRequest>) -> impl IntoResponse {
    let findings = LADDER_AUDITOR.audit_code(&payload.file, &payload.content);
    let report = AuditReport::new("anti-slop-rust-ladder", findings);
    (StatusCode::OK, Json(report))
}

async fn triage_handler(Json(payload): Json<TriageRequest>) -> impl IntoResponse {
    let allowed_refs = map_allowed_refs(payload.allowed_files.as_ref());

    let report = crate::triage_diff(
        &payload.diff,
        allowed_refs.as_deref(),
        payload.read_only,
    );
    (StatusCode::OK, Json(report))
}

pub fn create_router() -> Router {
    Router::new()
        .route("/health", get(health_handler))
        .route("/v1/shit-check", post(shit_check_handler))
        .route("/v1/ladder-audit", post(ladder_audit_handler))
        .route("/v1/triage", post(triage_handler))
}

pub async fn run_server(port: u16) -> Result<(), Box<dyn std::error::Error>> {
    let app = create_router();
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let listener = tokio::net::TcpListener::bind(addr).await?;
    println!("anti-slop-rust daemon listening on http://{}", addr);
    axum::serve(listener, app).await?;
    Ok(())
}
