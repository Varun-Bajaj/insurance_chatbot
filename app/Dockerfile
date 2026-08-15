FROM python:3.10.16

RUN mkdir -p app

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir --upgrade -r requirement.txt

EXPOSE 5559

CMD ["python", "main.py"]