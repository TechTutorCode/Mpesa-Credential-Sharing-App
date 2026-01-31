FROM python:3.12
WORKDIR /code
COPY requirements.txt /code/
RUN pip install -r /code/requirements.txt
COPY . /code
ENV PYTHONPATH=/code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
