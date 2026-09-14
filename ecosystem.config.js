module.exports = {
  apps: [
    {
      name: "shunde-poc",
      cwd: "/root/shunde-poc",
      script: ".venv/bin/uvicorn",
      args: "poc.web.app:app --host 127.0.0.1 --port 8220",
      interpreter: "none",
      env: {
        POC_WORKSPACE: "/root/shunde-poc/data",
        POC_LOAD_SECRETS: "0",
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
