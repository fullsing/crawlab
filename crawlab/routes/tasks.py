import json

import requests
from celery.worker.control import revoke

from constants.task import TaskStatus
from db.manager import db_manager
from routes.base import BaseApi
from utils import jsonify
from utils.spider import get_spider_col_fields


class TaskApi(BaseApi):
    col_name = 'tasks'

    arguments = (
        ('deploy_id', str),
        ('file_path', str)
    )

    def get(self, id=None, action=None):
        # action by id
        if action is not None:
            if not hasattr(self, action):
                return {
                           'status': 'ok',
                           'code': 400,
                           'error': 'action "%s" invalid' % action
                       }, 400
            return getattr(self, action)(id)

        elif id is not None:
            task = db_manager.get('tasks', id=id)
            spider = db_manager.get('spiders', id=str(task['spider_id']))
            task['spider_name'] = spider['name']
            try:
                with open(task['log_file_path']) as f:
                    task['log'] = f.read()
            except Exception as err:
                task['log'] = ''
            return jsonify(task)

        # list tasks
        args = self.parser.parse_args()
        page_size = args.get('page_size') or 10
        page_num = args.get('page_num') or 1
        tasks = db_manager.list('tasks', {}, limit=page_size, skip=page_size * (page_num - 1), sort_key='create_ts')
        items = []
        for task in tasks:
            # _task = db_manager.get('tasks_celery', id=task['_id'])
            _spider = db_manager.get('spiders', id=str(task['spider_id']))
            if task.get('status') is None:
                task['status'] = TaskStatus.UNAVAILABLE
            task['spider_name'] = _spider['name']
            items.append(task)
        return {
            'status': 'ok',
            'total_count': db_manager.count('tasks', {}),
            'page_num': page_num,
            'page_size': page_size,
            'items': jsonify(items)
        }

    def on_get_log(self, id):
        try:
            task = db_manager.get('tasks', id=id)
            with open(task['log_file_path']) as f:
                log = f.read()
                return {
                    'status': 'ok',
                    'log': log
                }
        except Exception as err:
            return {
                       'code': 500,
                       'status': 'ok',
                       'error': str(err)
                   }, 500

    def get_log(self, id):
        task = db_manager.get('tasks', id=id)
        node = db_manager.get('nodes', id=task['node_id'])
        r = requests.get('http://%s:%s/api/tasks/%s/on_get_log' % (
            node['ip'],
            node['port'],
            id
        ))
        if r.status_code == 200:
            data = json.loads(r.content.decode('utf-8'))
            return {
                'status': 'ok',
                'log': data.get('log')
            }
        else:
            data = json.loads(r.content)
            return {
                       'code': 500,
                       'status': 'ok',
                       'error': data['error']
                   }, 500

    def get_results(self, id):
        args = self.parser.parse_args()
        page_size = args.get('page_size') or 10
        page_num = args.get('page_num') or 1

        task = db_manager.get('tasks', id=id)
        spider = db_manager.get('spiders', id=task['spider_id'])
        col_name = spider.get('col')
        if not col_name:
            return []
        fields = get_spider_col_fields(col_name)
        items = db_manager.list(col_name, {'task_id': id})
        return {
            'status': 'ok',
            'fields': jsonify(fields),
            'total_count': db_manager.count(col_name, {'task_id': id}),
            'page_num': page_num,
            'page_size': page_size,
            'items': jsonify(items)
        }

    def stop(self, id):
        revoke(id, terminate=True)
        return {
            'id': id,
            'status': 'ok',
        }
