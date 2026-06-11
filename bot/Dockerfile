FROM python:3.12-slim
RUN pip install --no-cache-dir requests==2.32.3
WORKDIR /app
COPY grafy_bot.py /app/grafy_bot.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/app/grafy_bot.py"]
