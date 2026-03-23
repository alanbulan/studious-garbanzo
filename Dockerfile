FROM python:3.10

WORKDIR /code

# Install dependencies before copying the rest to use Docker cache better
COPY requirements.txt .

# Upgrade pip and install requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create a non-root user
# Hugging Face Spaces require running as a non-root user
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user:user . .

# Change permissions to ensure the app has read/write access everywhere
RUN chmod -R 777 $HOME/app

ENV PORT=7860
EXPOSE 7860

CMD ["python", "webui.py"]
