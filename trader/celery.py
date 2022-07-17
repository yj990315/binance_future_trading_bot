from __future__ import absolute_import, unicode_literals
from celery import Celery

# '셀러리' 프로그램을 위해 기본 장고 설정파일을 설정합니다.
app = Celery(
    'trader',
    broker_url = 'pyamqp://',
    result_backend='rpc://',
    result_expires=3600,
    include=['trader.tasks'],
    worker_cancel_long_running_tasks_on_connection_loss=True
)

# 등록된 장고 앱 설정에서 task를 불러옵니다.
app.autodiscover_tasks()


if __name__ == '__main__':
    app.start()
