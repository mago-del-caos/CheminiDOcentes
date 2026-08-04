# Usamos una versión ligera de Python
FROM python:3.11-slim

# Creamos un usuario normal (Hugging Face lo exige por seguridad)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Nos movemos a la carpeta de trabajo
WORKDIR /app

# Copiamos el archivo de dependencias y lo instalamos
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copiamos el resto del código
COPY --chown=user . .

# Exponemos el puerto 7860 (Hugging Face usa este por defecto)
EXPOSE 7860

# Comando para arrancar Streamlit con los ajustes para Docker
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]