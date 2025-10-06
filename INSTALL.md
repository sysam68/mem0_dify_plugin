# Mem0 Dify Plugin v0.0.3 - 安装指南

## 📦 安装步骤

### 1. 获取插件包

插件已打包为 `.difypkg` 文件：
- **文件名**: `mem0-0.0.3.difypkg`
- **大小**: ~600KB
- **位置**: `/Users/howsun/Warp/dify/mem0-plugin-update/`

### 2. 上传到 Dify

#### 方法 A：通过 Dify 管理界面（推荐）

1. **登录 Dify**
   - 访问你的 Dify 实例（Self-hosted 或 SaaS）
   - 例如：`https://your-dify-instance.com` 或 `https://cloud.dify.ai`

2. **进入插件管理**
   - 导航到 **Settings** → **Plugins**
   - 或直接访问 `/plugins` 路径

3. **上传插件**
   - 点击 **"Upload Plugin"** 或 **"安装插件"** 按钮
   - 选择 `mem0-0.0.3.difypkg` 文件
   - 等待上传和安装完成

4. **配置 API Key**
   - 安装完成后，点击插件的配置按钮
   - 输入你的 **Mem0 API Key**
   - 保存配置

#### 方法 B：使用 Dify CLI（如果可用）

```bash
# 如果你有 dify-cli 工具
dify plugin install mem0-0.0.3.difypkg
```

---

## 🔑 获取 Mem0 API Key

1. 访问 [Mem0 AI Dashboard](https://app.mem0.ai/dashboard/api-keys)
2. 注册或登录账号
3. 进入 **API Keys** 页面
4. 创建新的 API Key
5. 复制并保存 API Key

---

## ✅ 验证安装

安装完成后，你应该能看到以下 8 个工具：

### 核心功能工具
1. ✅ **Add Memory** - 添加记忆
2. ✅ **Retrieve Memory** - 搜索记忆（支持 v2 高级过滤）
3. ✅ **Get All Memories** - 获取所有记忆
4. ✅ **Get Memory** - 获取单条记忆详情
5. ✅ **Update Memory** - 更新记忆
6. ✅ **Delete Memory** - 删除单条记忆
7. ✅ **Delete All Memories** - 批量删除记忆
8. ✅ **Get Memory History** - 查看记忆历史

---

## 🧪 快速测试

### 测试 1：添加记忆
```json
{
  "user": "I love Italian food",
  "assistant": "Great! I'll remember that.",
  "user_id": "test_user_001",
  "metadata": "{\"category\": \"food_preferences\"}"
}
```

### 测试 2：搜索记忆
```json
{
  "query": "What food does the user like?",
  "user_id": "test_user_001",
  "version": "v1"
}
```

### 测试 3：使用 v2 高级过滤
```json
{
  "query": "user preferences",
  "version": "v2",
  "filters": "{\"AND\": [{\"user_id\": \"test_user_001\"}]}"
}
```

---

## 🔧 故障排查

### 问题 1：上传失败
**原因**：文件损坏或格式不正确
**解决**：
```bash
# 重新生成插件包
cd /Users/howsun/Warp/dify/mem0-plugin-update
./build_package.sh
```

### 问题 2：工具无法使用
**原因**：API Key 未配置或无效
**解决**：
1. 检查 Mem0 API Key 是否正确
2. 确认 API Key 有效且未过期
3. 在插件设置中重新输入 API Key

### 问题 3：v2 过滤器报错
**原因**：JSON 格式错误
**解决**：
- 确保 `filters` 参数是有效的 JSON 字符串
- 使用在线 JSON 验证器检查格式
- 参考 CHANGELOG.md 中的示例

### 问题 4：HTTP 超时
**原因**：网络连接问题或 API 响应慢
**解决**：
- 检查网络连接
- 确认可以访问 `api.mem0.ai`
- 插件默认超时为 30 秒，应该足够

---

## 📚 更多资源

- **插件更新日志**: 查看 `CHANGELOG.md`
- **Mem0 官方文档**: https://docs.mem0.ai
- **Dify 插件文档**: https://docs.dify.ai/docs/plugins
- **问题反馈**: 联系插件开发者

---

## 🔄 更新插件

### 从旧版本升级

如果你已经安装了 v0.0.2 或更早版本：

1. **备份数据**（可选）
   - 导出现有的记忆数据
   - 记录当前配置

2. **卸载旧版本**
   - 在 Dify 插件管理中卸载旧版本
   - 或使用 CLI：`dify plugin uninstall mem0`

3. **安装新版本**
   - 按照上述步骤安装 v0.0.3
   - 重新配置 API Key

4. **验证功能**
   - 测试新增的 6 个工具
   - 尝试 v2 高级过滤功能
   - 验证元数据支持

### 向后兼容性
✅ **好消息**：v0.0.3 完全向后兼容！
- 所有 v0.0.2 的工作流继续正常运行
- 无需修改现有配置
- 新参数均为可选

---

## 🎉 开始使用

安装完成后，你可以：

1. **在 Workflow 中使用**
   - 拖拽 Mem0 工具到工作流
   - 配置参数
   - 连接其他节点

2. **在 Agent 中使用**
   - 为 Agent 添加 Mem0 工具
   - Agent 将自动使用记忆功能
   - 支持长期记忆和上下文

3. **通过 API 调用**
   - 使用 Dify API 调用 Mem0 工具
   - 集成到你的应用中
   - 实现自定义记忆逻辑

---

## ⚠️ 重要提示

1. **API Key 安全**
   - 不要在公共场合分享 API Key
   - 定期更换 API Key
   - 使用环境变量存储敏感信息

2. **记忆管理**
   - 定期清理不需要的记忆
   - 使用 metadata 组织记忆
   - 注意记忆存储配额

3. **性能优化**
   - 使用 limit 参数控制返回数量
   - 合理使用过滤器减少查询范围
   - 避免频繁的全量查询

---

**祝你使用愉快！** 🚀

如有问题，请查看 CHANGELOG.md 或联系支持团队。
