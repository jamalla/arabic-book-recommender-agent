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

This is exactly how the live app was deployed (us-east-1). Steps 2 and 4 run in **AWS CloudShell**,
which already has Docker, the AWS CLI and your login. The names are the ones this project used.

**1. Image registry.** Amazon ECR, Create repository `arabic-book-recommender`, image tags **Immutable**
(a pushed `v1` can never be silently replaced; every release gets a new tag).

**2. Build, smoke-test and push the image** (build about 3 minutes, image 737 MB):

```bash
git clone --depth 1 https://github.com/jamalla/arabic-book-recommender-agent.git
cd arabic-book-recommender-agent/deploy
python3 sync.py --check                                   # the agent copy must match the evaluated code
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
IMAGE=$ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/arabic-book-recommender:v1
docker build -t $IMAGE .
docker run -d --name smoke -p 8080:8080 -e OPENAI_API_KEY=dummy $IMAGE   # no real keys needed
sleep 60; curl -s localhost:8080/health; docker rm -f smoke               # {"status":"ok",...}
aws ecr get-login-password | docker login --username AWS --password-stdin ${IMAGE%%/*}
docker push $IMAGE
docker logout ${IMAGE%%/*}                                # do not leave the registry token behind
```

**3. Keys.** Secrets Manager, Store a new secret, **Other type of secret**, three key/value pairs
(`OPENAI_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`), Next, secret name
`arabic-book-recommender/app`, Next, no rotation, Next, **Store**. Only the owner of the keys types the values.

**4. Two IAM roles, least privilege.** The execution role starts the container and may read **this one
secret**; the infrastructure role lets Express Mode build the load balancer, certificate and security groups.

```bash
SECRET_ARN=$(aws secretsmanager describe-secret --secret-id arabic-book-recommender/app --query ARN --output text)

aws iam create-role --role-name arabic-book-recommender-execution --assume-role-policy-document \
  '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name arabic-book-recommender-execution \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam put-role-policy --role-name arabic-book-recommender-execution --policy-name read-app-secret --policy-document \
  "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"secretsmanager:GetSecretValue\",\"Resource\":\"$SECRET_ARN\"}]}"

aws iam create-role --role-name arabic-book-recommender-infrastructure --assume-role-policy-document \
  '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name arabic-book-recommender-infrastructure \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices
```

**5. The service.** Amazon ECS, Express Mode:

| Field | Value |
|---|---|
| Image URI | `$IMAGE` from step 2 |
| Task execution role, Infrastructure role | the two roles from step 4 |
| Additional configurations, Name | `arabic-book-recommender` (cluster left empty: Express Mode creates `default`) |
| Container port, Health check path | `8080`, `/health` |
| Environment variables, value type *Environment variable* | `LANGFUSE_TRACING_ENVIRONMENT` = `production`, `LANGFUSE_BASE_URL` = `https://cloud.langfuse.com` |
| Environment variables, value type *Secret* | `OPENAI_API_KEY` = `<SECRET_ARN>:OPENAI_API_KEY::`, the same for the two Langfuse keys |
| CPU, Memory | 0.5 vCPU, 1 GB |
| Minimum, maximum number of tasks | 1, 1 |
| Tags | `project` = `arabic-book-recommender` (makes the clean-up easy to find) |

Express Mode then creates the cluster, an HTTPS load balancer with a certificate, security groups, a log group
and auto scaling, and shows the **Application URL** (`https://<id>.ecs.us-east-1.on.aws`). The first deployment
took about 7 minutes; the URL answers `503` until the container passes `/health` five times in a row.

**6. Check it.** Chat once and click 👍/👎: Langfuse shows a new session in environment `production` (one
trace per question, every `search_books` call, tokens and cost) and a `user_feedback` score on the answer.

**Why exactly one task?** Gradio keeps each open chat in the memory of its container. With two tasks the
load balancer could send one chat's requests to both, so more tasks would first need sticky sessions.

**The real cost guard** is a monthly budget on the OpenAI key: the per-chat limit only keeps each
conversation short, and anyone can start a new chat. The AWS side costs about $1.5 a day while it runs
(load balancer, Fargate task, public IPs).

**Update:** change the code, run `python deploy/sync.py`, build and push `:v2` (step 2), then
Express Mode service, Update service, new image URI.
**Remove:** delete the Express Mode service (it removes its load balancer, certificate and security groups),
then the `default` cluster, the ECR repository, the secret, the two roles and the log group.
