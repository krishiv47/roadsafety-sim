# Deploying to Google Cloud Run

One-time setup:
  1. Install gcloud CLI:  https://cloud.google.com/sdk/docs/install
  2. gcloud auth login
  3. gcloud config set project YOUR_PROJECT_ID

Deploy (from inside roadsafety_sim/):

  gcloud run deploy roadsafety-ai \
    --source . \
    --region asia-south1 \
    --port 8000 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --allow-unauthenticated

That's it — gcloud builds the Dockerfile in the cloud (no local Docker
needed) and gives you a public https URL. WebSockets work on Cloud Run,
so the live map updates exactly like localhost.

Notes:
- asia-south1 = Mumbai (lowest latency for India demos)
- 2Gi memory is required for YOLOv8s inference
- First request after idle takes ~20 s (model load); add --min-instances 1
  to keep it always warm (costs more)
- AI Copilot: paste your Groq key in the Copilot tab UI, or bake it in by
  rebuilding the frontend with VITE_GROQ_API_KEY set in frontend/.env
