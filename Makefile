NAME ?= prefix

build:
	./build.sh

deploy:
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

update:

	$(eval STACK_NAME="alb-accesslog-aggregator-${NAME}")
	$(eval TEMPLATE_FILE := file://$(shell readlink -f ./cloudformation/template.yaml))
	$(eval PARAMETERS_FILE := file://cloudformation/parameters/params.json)
	aws cloudformation create-change-set --stack-name $(STACK_NAME) --template-body $(TEMPLATE_FILE) --parameters $(PARAMETERS_FILE) --change-set-name "mychangeset" --capabilities CAPABILITY_NAMED_IAM
	aws cloudformation wait change-set-create-complete --stack-name $(STACK_NAME) --change-set-name "mychangeset"
