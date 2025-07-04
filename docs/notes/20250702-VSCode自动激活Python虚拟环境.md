# VSCode自动激活Python虚拟环境配置

## 问题背景

用户希望在VSCode中打开新的命令行窗口时，能够自动执行`.venv/Scripts/activate`来激活Python虚拟环境，避免每次手动激活的麻烦。

## 尝试的解决方案

### 方案1：使用VSCode Python扩展的自动激活功能

通过配置VSCode的settings.json文件，启用Python扩展的自动环境激活功能：

```json
{
  "python.terminal.activateEnvironment": true,
  "python.terminal.activateEnvInCurrentTerminal": true
}
```

- `python.terminal.activateEnvironment`: 在所有新创建的终端中自动激活Python环境
- `python.terminal.activateEnvInCurrentTerminal`: 在扩展加载时激活当前终端中的Python环境

### 前提条件

1. 项目中已经创建了`.venv`虚拟环境
2. 安装了VSCode的Python扩展
3. Python扩展能够检测到虚拟环境

### 补充操作

- 可以使用`Ctrl+Shift+P`打开命令面板，执行`Python: Select Interpreter`手动选择虚拟环境中的Python解释器
- 确保`.venv`文件夹在项目根目录下，便于VSCode自动检测

## 经验总结

### 有效方法
1. **优先使用Python扩展的内置功能**：VSCode的Python扩展已经提供了完善的虚拟环境自动激活功能，无需复杂配置
2. **确保环境检测**：虚拟环境需要被正确检测，建议将`.venv`文件夹放在项目根目录
3. **正确选择解释器**：通过命令面板选择正确的Python解释器路径

### 注意事项
1. 在Windows环境下，虚拟环境激活脚本位于`.venv/Scripts/activate`
2. 确保Python扩展版本较新，以获得最佳的自动激活体验
3. 如果自动激活不生效，可以尝试重新加载VSCode窗口

### 配置位置
- 全局配置：VSCode用户设置
- 项目配置：项目根目录下的`.vscode/settings.json`

推荐使用项目配置，确保团队成员都能享受到相同的开发体验。