FROM python:3.10-slim 

WORKDIR /usr/local/app

COPY ./ ./

COPY requirements.txt ./ 
RUN pip install --no-cache-dir -r requirements.txt

RUN chmod -R 777 /usr/local/app

EXPOSE 8000

CMD ["uvicorn", "servidor_central.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
