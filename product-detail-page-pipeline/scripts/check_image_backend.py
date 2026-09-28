#!/usr/bin/env python3
"""Read-only AI Creative MCP model/canvas preflight; never submits generation."""
import argparse
import json
import sys
from aicreative_mcp import Client, MCPError, model_default, ratio_for_size, validate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url', '--mcp-url', dest='url')
    p.add_argument('--model', default=model_default('image'), type=int)
    p.add_argument('--endpoint', choices=['mcp'], default='mcp')
    p.add_argument('--operation', action='append', choices=['generate', 'edit'], default=[])
    p.add_argument('--size', action='append', default=[])
    p.add_argument('--supported-sizes', default='1024x1024,1024x1536,1536x1024')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--timeout', type=int, default=30)
    args=p.parse_args()
    result={'ok':False,'provider':'aicreative-mcp','modelConfigId':args.model,'offline':args.offline,'errors':[],
            'sizeSemantics':'Canvas hints specify ratios; model resolution tiers determine actual dimensions.'}
    try:
        unsupported=set(args.size)-set(args.supported_sizes.split(','))
        if unsupported:
            raise MCPError('Unsupported requested size hint(s): '+', '.join(sorted(unsupported)))
        ratios=[ratio_for_size(size) for size in args.size]
        if args.model <= 0:
            raise MCPError('modelConfigId must be positive')
        if not args.offline:
            client=Client(args.url,args.timeout)
            model=client.call('get_model_parameters',{'modelConfigId':args.model})['model']
            for ratio in ratios or ['1:1']:
                validate({'generationType':'IMAGE','prompt':'Backend capability check',
                          'parameters':{'count':1,'aspectRatioKey':ratio,'publicVisibilityKey':'OFF'}},model,[])
            if 'edit' in args.operation and not model['inputSettings']['image'].get('visibility'):
                raise MCPError('Selected model does not accept reference images')
            result['modelDefinition']=model
        result['ok']=True
    except (MCPError,ValueError) as exc:
        result['errors'].append(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
