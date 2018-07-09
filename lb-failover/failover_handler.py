import os
import json
import boto3

elb = boto3.client("elbv2")

def lambda_handler(event, context):
    region = os.environ['AWS_REGION']

    tg_fallback = os.environ['TG_FALLBACK']
    
    message = json.loads(event['Records'][0]['Sns']['Message'])
    alarm = message['NewStateValue']
    account = message['AWSAccountId']

    trigger = message['Trigger']
    for dimension in trigger['Dimensions']:
        if dimension['name'] == 'LoadBalancer':
            lb = f"arn:aws:elasticloadbalancing:{region}:{account}:loadbalancer/" + dimension['value']
            lb_type = dimension['value'][:dimension['value'].index("/")]

    for dimension in trigger['Dimensions']:
        if dimension['name'] == 'TargetGroup':
            tg_primary = f"arn:aws:elasticloadbalancing:{region}:{account}:" + dimension['value']
        
    def failoverRule(rule, from_target, to_target):
        ruleArn = rule['RuleArn']
        print(f'Failing over {ruleArn}({lb}) from {from_target} to {to_target}')
        actions = rule['Actions']
        for action in actions:
            if action['TargetGroupArn'] == from_target:
                action['TargetGroupArn'] = to_target
            
        elb.modify_rule(RuleArn=ruleArn, Actions=actions)
        print(f'Failed over {ruleArn}({lb}) from {from_target} to {to_target}')
    
    def failoverListener(listener, from_target, to_target):
        listenerArn = listener['ListenerArn']
        print(f'Failing over {listenerArn}({lb}) from {from_target} to {to_target}')
        actions = listener['DefaultActions']
        for action in actions:
            if action['TargetGroupArn'] == from_target:
                action['TargetGroupArn'] = to_target
        
        elb.modify_listener(ListenerArn=listenerArn, DefaultActions=actions)
        print(f'Failed over {listenerArn}({lb}) from {from_target} to {to_target}')
    
    def filterRules(rules, targetGroup):
        return [rule['RuleArn'] for rule in rules if targetGroup in [action['TargetGroupArn'] for action in rule['Actions']]]
    
    def filterListeners(listeners, targetGroup):
        return [listener for listener in listeners if targetGroup in [action['TargetGroupArn'] for action in listener['DefaultActions']]]
    
    if not tg_fallback.startswith('arn:'):
        tg_fallback = elb.describe_target_groups(Names=[tg_fallback])['TargetGroups'][0]['TargetGroupArn']
    
    listeners = [listener for listener in elb.describe_listeners(LoadBalancerArn=lb)['Listeners']]
    for listener in listeners:
        if alarm == 'ALARM':
            [failoverListener(listener, tg_primary, tg_fallback) for listener in filterListeners(listeners, tg_primary)]
        elif alarm == 'OK':
            [failoverListener(listener, tg_fallback, tg_primary) for listener in filterListeners(listeners, tg_fallback)]
            
        if not lb_type == 'net':
            rules = rules + elb.describe_rules(ListenerArn=listener['ListenerArn'])['Rules']
            if alarm == 'ALARM':
                [failoverRule(rule, tg_primary, tg_fallback) for rule in filterRules(rules, tg_primary)]
            elif alarm == 'OK':
                [failoverRule(rule, tg_fallback, tg_primary) for rule in filterRules(rules, tg_fallback)]
