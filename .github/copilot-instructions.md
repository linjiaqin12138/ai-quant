# General Development Guidelines
- 我们在windows下进行开发，执行命令行命令的时候注意使用powershell下可以执行的命令，语法上不要和Linux下的命令冲突。比如不能出现`&&`之类的语法。
- 保持与现有代码风格、代码实现方案的一致性，可以参考同一文件夹下其它模块的代码。

# Folder Structure
- docs/notes目录用来存放笔记，每当用户要求你总结笔记时，请创建一个markdown笔记文件`日期-主题.md`, 内容包括：
    - 问题背景
    - 尝试的解决方案
    - 经验总结（如与用户的沟通、一些有效的方法、以后应该注意怎么做等）
- lib/: 项目的核心代码，主要是各类工具类和业务逻辑的实现
    - adapter：适配器，主要是将不同的API或数据源适配到统一的接口上，包括分布式锁，数据库访问，大模型，新闻模块，交易所接口，通知等
    - config.py：读取配置的统一入口，主要是读取配置文件和环境变量
    - tools/: 一些通用的工具函数，且具有副作用
    - model/: 存放一些数据结构、业务模型等
    - utils/: 一些通用的工具函数，不具有副作用
    - logger.py：日志记录的统一入口，打日志必须使用
    - modules/: 复杂功能模块，整合adapter、model、utils等的调用，并提供简洁接口
- scripts/: 存放一些命令行文件等，还有做一些实验性的功能（可能引入一些其它的第三方库啥的），比如scripts/tauric_trading_agent
- tests/: pytest测试用例，主要是对lib/中的代码进行测试
- notebook: 一些在jupyter notebook中做的笔记和实验记录，AI请忽略