
import argparse
from lib.adapter.notification import PushPlus

from lib.modules.notification_logger import NotificationLogger
from lib.strategys.simple_turtle import run
from lib.utils.file import read_json_file

def parse_command_line() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description='海龟交易法程序')
  parser.add_argument('--config', type=str, help='配置文件路径')

  args = parser.parse_args()

  if not args.config:
    parser.print_help()
    exit()

  return args

def main():
    args = parse_command_line()
    cfg = read_json_file(args.config)
    frame = cfg['frame']
    items = cfg['items']

    with NotificationLogger(f'海龟交易法 {frame}', PushPlus()) as logger:
       for params in items:
          params.update({ 'data_frame': frame })
          run(params, logger)
    
main()