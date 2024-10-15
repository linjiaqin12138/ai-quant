
import argparse
from lib.adapter.notification import PushPlus, NotificationAbstract

from lib.modules.notification_logger import NotificationLogger
from lib.strategys.gpt import run
from lib.utils.file import read_json_file

def parse_command_line() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description='GPT交易法程序')
  parser.add_argument('--config', type=str, help='配置文件路径')

  args = parser.parse_args()

  if not args.config:
    parser.print_help()
    exit()

  return args

def main():
    args = parse_command_line()
    cfg = read_json_file(args.config)

    with NotificationLogger(f'GPT交易法 {cfg.get("symbol")}', PushPlus()) as logger:
        run(cfg, logger)
    
main()