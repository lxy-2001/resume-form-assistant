# Browser Extension

浏览器扩展模块。负责当前页面的字段扫描、结果展示、受控填写、审校交互和撤销；不直接调用模型。

计划的主要区域：`background/`、`content/`、`sidepanel/`、`options/`。

## 本地开发

```powershell
cd apps/extension
npm install
npm test -- --run
npm run typecheck
npm run lint
npm run build
```

F001 的 Options Page 用于维护本地资料、查看元数据、受控导出和确认删除；扩展 UI 不直接调用模型。

F001 当前交付的是可独立运行的 Vite Options Page，不包含浏览器扩展 manifest、content
script 或商店打包物。安装为 Chrome/Edge 扩展属于后续 F004/F017；打包后需要在本地服务中
把对应的精确扩展 origin 加入 `RESUME_AGENT_ALLOWED_ORIGINS`，不能使用 `*`。

## 操作边界

- 页面已有值默认不覆盖；不确定的候选必须等待用户确认。
- 导出和删除都显示范围并要求明确确认；导出目标是本地文件，删除全部资料不可撤销。
- 扩展只负责展示和发起受控操作，资料解析、校验和存储由本地 Agent 处理。
- 不配置或不允许远程模型时，F001 的本地资料维护仍可使用。
