param(
    [string]$ProjectId = "civil-ai-agent",
    [string]$Region = "asia-south1",
    [string]$ServiceName = "civil-ai-agent",
    [string]$Repository = "civil-ai-agent",
    [int]$MinInstances = 0,
    [int]$MaxInstances = 1,
    [int]$Concurrency = 2,
    [int]$TimeoutSeconds = 900,
    [string]$Memory = "1Gi",
    [string]$Cpu = "0.5"
)

$ErrorActionPreference = "Stop"
$requirementsFile = "requirements-gcloud.txt"

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Install it and retry."
    }
}

function Set-Or-UpdateSecret {
    param(
        [string]$Name,
        [string]$Value,
        [string]$ProjectId
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        Write-Host "Skipping secret '$Name' because no value was provided." -ForegroundColor Yellow
        return
    }

    $exists = $false
    try {
        gcloud secrets describe $Name --project $ProjectId | Out-Null
        $exists = $true
    }
    catch {
        $exists = $false
    }

    if (-not $exists) {
        $Value | gcloud secrets create $Name --project $ProjectId --data-file=- --replication-policy=automatic | Out-Null
        Write-Host "Created secret '$Name'." -ForegroundColor Green
    }
    else {
        $Value | gcloud secrets versions add $Name --project $ProjectId --data-file=- | Out-Null
        Write-Host "Updated secret '$Name' with a new version." -ForegroundColor Green
    }
}

Require-Command -Name "gcloud"
Require-Command -Name "docker"

Write-Host "Configuring project and APIs..." -ForegroundColor Cyan

gcloud config set project $ProjectId | Out-Null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com --project $ProjectId | Out-Null

Write-Host "Ensuring Artifact Registry repository exists..." -ForegroundColor Cyan
$repoExists = $false
try {
    gcloud artifacts repositories describe $Repository --location $Region --project $ProjectId | Out-Null
    $repoExists = $true
}
catch {
    $repoExists = $false
}

if (-not $repoExists) {
    gcloud artifacts repositories create $Repository --location $Region --repository-format docker --project $ProjectId | Out-Null
    Write-Host "Created Artifact Registry repository '$Repository'." -ForegroundColor Green
}
else {
    Write-Host "Artifact Registry repository '$Repository' already exists." -ForegroundColor DarkGray
}

Write-Host "Enter secret values. Press Enter to skip any optional value." -ForegroundColor Cyan

$secretValues = @{
    OPENAI_TOKEN     = Read-Host "OPENAI_TOKEN"
    HF_TOKEN         = Read-Host "HF_TOKEN"
    BREVO_API_KEY    = Read-Host "BREVO_API_KEY"
    BREVO_FROM_EMAIL = Read-Host "BREVO_FROM_EMAIL"
    BREVO_FROM_NAME  = Read-Host "BREVO_FROM_NAME (default: Civil-AI-Agent)"
    RESEND_API_KEY   = Read-Host "RESEND_API_KEY"
    EMAIL_FROM       = Read-Host "EMAIL_FROM (default: onboarding@resend.dev)"
    ADMIN_SEED_EMAIL = Read-Host "ADMIN_SEED_EMAIL"
}

if ([string]::IsNullOrWhiteSpace($secretValues.BREVO_FROM_NAME)) {
    $secretValues.BREVO_FROM_NAME = "Civil-AI-Agent"
}

if ([string]::IsNullOrWhiteSpace($secretValues.EMAIL_FROM)) {
    $secretValues.EMAIL_FROM = "onboarding@resend.dev"
}

Write-Host "Creating/updating secrets..." -ForegroundColor Cyan
foreach ($entry in $secretValues.GetEnumerator()) {
    Set-Or-UpdateSecret -Name $entry.Key -Value $entry.Value -ProjectId $ProjectId
}

Write-Host "Granting Cloud Run runtime service account access to secrets..." -ForegroundColor Cyan
$projectNumber = gcloud projects describe $ProjectId --format "value(projectNumber)"
$runtimeSa = "$projectNumber@cloudrun.gserviceaccount.com"

foreach ($secretName in $secretValues.Keys) {
    if ([string]::IsNullOrWhiteSpace($secretValues[$secretName])) {
        continue
    }

    gcloud secrets add-iam-policy-binding $secretName --project $ProjectId --member "serviceAccount:$runtimeSa" --role "roles/secretmanager.secretAccessor" --quiet | Out-Null
}

Write-Host "Building and pushing image..." -ForegroundColor Cyan
$image = "$Region-docker.pkg.dev/$ProjectId/$Repository/$ServiceName:latest"
gcloud auth configure-docker "$Region-docker.pkg.dev" --quiet | Out-Null
if (-not (Test-Path $requirementsFile)) {
    throw "Required file '$requirementsFile' was not found."
}

docker build --build-arg REQUIREMENTS_FILE=$requirementsFile -t $image .
docker push $image

Write-Host "Deploying to Cloud Run..." -ForegroundColor Cyan

$deployArgs = @(
    "run", "deploy", $ServiceName,
    "--image=$image",
    "--region=$Region",
    "--platform=managed",
    "--memory=$Memory",
    "--cpu=$Cpu",
    "--min-instances=$MinInstances",
    "--max-instances=$MaxInstances",
    "--concurrency=$Concurrency",
    "--timeout=$TimeoutSeconds",
    "--cpu-throttling",
    "--no-cpu-boost",
    "--allow-unauthenticated",
    "--port=8080",
    "--set-env-vars=STREAMLIT_SERVER_HEADLESS=true,STREAMLIT_SERVER_ENABLEXSRFPROTECTION=false,STREAMLIT_SERVER_ENABLECORS=false"
)

foreach ($secretName in $secretValues.Keys) {
    if ([string]::IsNullOrWhiteSpace($secretValues[$secretName])) {
        continue
    }

    $deployArgs += "--set-secrets=$secretName=$secretName:latest"
}

gcloud @deployArgs

$serviceUrl = gcloud run services describe $ServiceName --region $Region --project $ProjectId --format "value(status.url)"

Write-Host "Deployment complete." -ForegroundColor Green
Write-Host "Service URL: $serviceUrl" -ForegroundColor Green
