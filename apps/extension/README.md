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

Options Page 同时提供 PDF/DOCX 导入：文件发送到本地 Agent 进行预览后，页面展示来源、证据、
置信度和已有值冲突。候选默认不写入，用户逐项接受或拒绝后才会提交确认；取消或关闭预览不会
修改资料库。图像型 PDF 是否使用 OCR 由本地服务报告，远程模型同意默认关闭。

F001 当前交付的是可独立运行的 Vite Options Page，不包含浏览器扩展 manifest、content
script 或商店打包物。安装为 Chrome/Edge 扩展属于后续 F004/F017；打包后需要在本地服务中
把对应的精确扩展 origin 加入 `RESUME_AGENT_ALLOWED_ORIGINS`，不能使用 `*`。

## 操作边界

- 页面已有值默认不覆盖；不确定的候选必须等待用户确认。
- 导出和删除都显示范围并要求明确确认；导出目标是本地文件，删除全部资料不可撤销。
- 扩展只负责展示和发起受控操作，资料解析、校验和存储由本地 Agent 处理。
- 不配置或不允许远程模型时，F001 的本地资料维护仍可使用。

F003 会在文档预览后增加本地标准化审阅：页面展示规范值、原始来源、置信度、问题和冲突，用户可以逐项接受、修改或拒绝；未确认的标准化结果不会写入资料库。
