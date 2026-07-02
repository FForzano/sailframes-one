# process_upload worker — CSV downsampling + session analysis.
# AWS Lambda base image: the same image deploys to Lambda (container image) and
# runs locally via the bundled Runtime Interface Emulator:
#   docker run -p 9000:8080 sailframes-process-upload
#   curl -XPOST localhost:9000/2015-03-31/functions/function/invocations -d @event.json
FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# handler.py + analyzer.py + processing/ (the analytics library moved here from
# the backend so the API stays pure-serving).
COPY . ${LAMBDA_TASK_ROOT}/

CMD ["handler.lambda_handler"]
