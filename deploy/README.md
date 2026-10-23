# Arabic Book Recommender: the deployable chat app

This folder is the **whole app on its own**: copy it anywhere, build it, run it. It does not need
the notebooks, the evaluation code or the data pipeline around it. Inside is the agent that won the
evaluation in Milestone 5 (LangGraph + prompt v2) behind an Arabic chat UI.

```text
deploy/
├── app/main.py        Gradio chat UI (Arabic, right-to-left) served by FastAPI, GET /health
├── bookrec/           the agent, the search_books tool and the agent factory
├── data/catalog.csv   the 200 books the agent may recommend
├── Dockerfile         python:3.11-slim, non-root user, port 8080
├── requirements.txt   runtime dependencies only
├── .env.example       every setting the app reads
└── sync.py            keeps bookrec/ and the catalog equal to the course code
```

## Settings

| Variable | Secret | Default | Purpose |
|---|:-:|---|---|
| `OPENAI_API_KEY` | yes | | the agent's model |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | yes | | traces, sessions, 👍/👎 scores |
| `LANGFUSE_BASE_URL` | | `https://cloud.langfuse.com` | Langfuse region |
| `LANGFUSE_TRACING_ENVIRONMENT` | | `default` | `production` on AWS, so app traces stay apart from tests |
| `OPENAI_MODEL` | | `gpt-6-luna` | |
| `AGENT_FRAMEWORK`, `PROMPT_VERSION` | | `langgraph`, `v2` | the evaluated winner (`openai`, `v1` also work) |
| `MAX_QUESTIONS_PER_CHAT` | | `15` | guard for an app that is open to anyone |
| `PORT` | | `8080` | |

## Run it locally

```bash
cd deploy
cp .env.example .env              # then put your keys in .env
docker build -t arabic-book-recommender .
docker run --rm -p 8080:8080 --env-file .env arabic-book-recommender
# chat: http://localhost:8080    health check: http://localhost:8080/health
```

## Deploy on AWS (ECS Express Mode)

1. **Image registry.** Amazon ECR, Create repository: `arabic-book-recommender` (private).
2. **Build and push** from AWS CloudShell, which already has Docker and your AWS login:

   ```bash
   git clone --depth 1 https://github.com/jamalla/arabic-book-recommender-agent.git
   cd arabic-book-recommender-agent/deploy
   python3 sync.py --check           # the agent copy must match the evaluated code
   ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
   IMAGE=$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/arabic-book-recommender:v1
   docker build -t $IMAGE .
   aws ecr get-login-password | docker login --username AWS --password-stdin ${IMAGE%%/*}
   docker push $IMAGE
   ```

3. **Keys.** Secrets Manager, Store a new secret, Other type of secret, three key/value pairs
   (`OPENAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`), name `arabic-book-recommender/app`.
4. **Service.** Amazon ECS, Express Mode, Create:
   - image: the URI from step 2; container port `8080`; health check path `/health`
   - environment variables: `LANGFUSE_TRACING_ENVIRONMENT=production` (the other settings have defaults)
   - secrets: each key from the secret in step 3 (`<secret ARN>:OPENAI_API_KEY::` and so on); the task
     execution role needs `secretsmanager:GetSecretValue` on that secret
   - size: 0.5 vCPU, 1 GB; tasks: minimum 1, maximum 1
5. **Open the HTTPS URL** that Express Mode shows. Every chat appears in Langfuse (environment
   `production`), one session per chat, with 👍/👎 as the `user_feedback` score.

**Why exactly one task?** Gradio keeps each open chat in the memory of its container. With two tasks the
load balancer could send one chat's requests to both, so more tasks would first need sticky sessions.

**The real cost guard** is a monthly budget on the OpenAI key: the per-chat limit only keeps each
conversation short, and anyone can start a new chat.

**Update:** change the code, run `python deploy/sync.py`, push a new tag (`:v2`) and point the service at it.
**Remove:** delete the Express Mode service (it removes its load balancer), the ECR repository and the secret.
