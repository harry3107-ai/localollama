Below is an **updated version of your README** optimized for **~4 GB available RAM** and using **DeepSeek Coder 1.3B**, which works well with **Ollama** inside **Docker**.

I also fixed a few mistakes (your README mentioned **6.7B while downloading 1.3B**).

---

# AI Dev Workspace

Local AI development environment using **Docker** and **Ollama** to run lightweight coding models like **DeepSeek Coder 1.3B** locally.

This setup allows you to run an AI coding assistant **offline** and connect it to your code editor.

Optimized for **low-memory systems (~4 GB available RAM)**.

---

# Project Structure

```
ai-dev-workspace/
│
├── docker/
│   └── docker-compose.yml
│
├── app/
│   └── test.py
│
├── prompts/
│   └── examples.md
│
└── README.md
```

---

# Requirements

Minimum setup:

* Docker installed
* Docker Compose
* **4 GB RAM available**
* Internet connection (only required for first model download)

Recommended:

* 8–16 GB RAM for larger models

---

# Start AI Server

Navigate to the docker folder:

```sh
cd docker
```

Start containers:

```sh
docker compose up -d
```

This starts **Ollama** locally on:

```
http://localhost:11434
```

---

# Check Running Containers

```sh
docker ps
```

Expected container:

```
ollama
```

---

# Check Installed Models

```sh
docker exec -it ollama ollama list
```

---

# Download Lightweight Coding Models

For **4 GB RAM systems**, use small models.

Recommended coding model:

```sh
docker exec -it ollama ollama pull deepseek-coder:1.3b
```

Optional additional lightweight models:

```sh
docker exec -it ollama ollama pull santacoder:1.1b
docker exec -it ollama ollama pull phi3:mini
```

Approximate memory usage:

| Model               | RAM Required | Use Case           |
| ------------------- | ------------ | ------------------ |
| deepseek-coder:1.3b | ~2–3 GB      | coding             |
| santacoder:1.1b     | ~2 GB        | lightweight coding |
| phi3:mini           | ~3–4 GB      | reasoning + coding |

---

# Verify Model Installation

```sh
docker exec -it ollama ollama list
```

Example output:

```
NAME                     SIZE
deepseek-coder:1.3b      ~2.3GB
```

---

# Run the Coding Model

Start an interactive session:

```sh
docker exec -it ollama ollama run deepseek-coder:1.3b
```

Example prompt:

```
Write a Python quicksort function
```

Exit the model:

```
/bye
```

---

# Test Ollama API

Local AI server runs at:

```
http://localhost:11434
```

Example API request:

```sh
curl http://localhost:11434/api/generate \
-d '{
"model":"deepseek-coder:1.3b",
"prompt":"write a python fibonacci function"
}'
```

---

# Stop the Server

```sh
docker compose down
```

---

# Useful Docker Commands

Start containers

```sh
docker compose up -d
```

Stop containers

```sh
docker compose down
```

Check containers

```sh
docker ps
```

Check images

```sh
docker images
```

---

# Run topic definition generator

Use `run_loop_definitions.py` to generate incremental definitions into `syllabus/ai_definitions.json`.

From project root:

```sh
python syllabus/run_loop_definitions.py
```

Options:

```sh
python syllabus/run_loop_definitions.py \
  --start-subject "Algebra" \
  --start-chapter "Equations" \
  --start-topic "Quadratic Equations"
```

This starts processing from the matching subject/chapter/topic (inclusive), while preserving existing definitions in `syllabus/ai_definitions.json`.

# Create a new Markdown file in the same directory

To add a new `.md` in the current directory:

```sh
cd syllabus
copy NUL new-file.md   # Windows
# OR
touch new-file.md      # Unix-like shells
```

# PowerShell Command History

Show command history:

```sh
Get-History
```

Run a previous command:

```sh
Invoke-History <id>
```

Example:

```sh
Invoke-History 2
```

---

# Example Setup History

Example commands used during setup:

```sh
docker compose up -d
docker images
docker exec -it ollama ollama list
docker exec -it ollama ollama pull deepseek-coder:1.3b
docker exec -it ollama ollama run deepseek-coder:1.3b
docker exec -it ollama ollama pull gemma:2b
docker exec -it ollama ollama run gemma:2b
```

Remove a model:

```sh
docker exec -it ollama ollama rm santacoder:1.1b
```

---

# Future Improvements

Possible extensions:

* Add web interface for AI chat (OpenWebUI)
* Add multiple AI models
* Connect to code editor AI extensions
* Add document search (RAG)
* Enable GPU acceleration
* Add automatic model selection

---

# Notes

* Models are stored inside a Docker volume.
* First download may take several minutes.
* Requires several GB of disk space.
* Works completely **offline after models are downloaded**.
* For low-RAM systems, keep **only one model loaded at a time**.

---

✅ If you want, I can also give you a **much better version of this project** that includes:

* **Open WebUI chat interface
* **VS Code AI integration**
* **local RAG document search**
* optimized **Docker setup for 4 GB RAM**

It becomes a **full local Copilot replacement**.
# localollama
cd syllabus
python generate_quizzes.py
