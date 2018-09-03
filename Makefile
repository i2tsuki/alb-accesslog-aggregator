NAME ?= prefix

deploy:
	rm -f ./lambda.zip

	python3 -m venv ./venv

	/bin/sh -c ". ./venv/bin/activate && pip3 install -r ./requirements.txt > /dev/null"

	mkdir -p ./archive
	rsync -aK --exclude '__pycache__' --exclude '.pyc' ./venv/lib/python3.6/site-packages/ ./archive/
	rsync -aK --exclude '__pycache__' --exclude '.pyc' ./src/ ./archive/

	/bin/sh -c "cd ./archive && zip -r ./lambda.zip . > /dev/null"

	mv ./archive/lambda.zip ./
	rm -rf ./archive

	declare -a FUNCTIONS="$$(aws lambda list-functions --query 'Functions[].FunctionArn' --output text)"; \
	for i in $${FUNCTIONS[@]}; \
	do \
	    APPLICATION="$$(aws lambda list-tags --resource $$i --query 'Tags.Application' --output text)"; \
	    if [ "$${APPLICATION}" = "alb-accesslog-aggregator" ]; then \
	        aws lambda update-function-code --function-name $$i --zip-file fileb://lambda.zip; \
	    fi \
	done

create:
	$(eval STACK_NAME="alb-accesslog-aggregator-${NAME}")
	$(eval TEMPLATE_FILE := file://$(shell readlink -f ./cloudformation/template.yaml))
	$(eval PARAMETERS_FILE := file://cloudformation/parameters/params.json)
	aws cloudformation create-stack --stack-name $(STACK_NAME) --template-body $(TEMPLATE_FILE) --parameters $(PARAMETERS_FILE) --capabilities CAPABILITY_NAMED_IAM
	aws cloudformation wait stack-create-complete --stack-name $(STACK_NAME)

create-changeset:
	$(eval STACK_NAME="alb-accesslog-aggregator-${NAME}")
	$(eval TEMPLATE_FILE := file://$(shell readlink -f ./cloudformation/template.yaml))
	$(eval PARAMETERS_FILE := file://cloudformation/parameters/params.json)
	aws cloudformation create-change-set --stack-name $(STACK_NAME) --template-body $(TEMPLATE_FILE) --parameters $(PARAMETERS_FILE) --change-set-name "changeset" --capabilities CAPABILITY_NAMED_IAM
	aws cloudformation wait change-set-create-complete --stack-name $(STACK_NAME) --change-set-name "mychangeset"
