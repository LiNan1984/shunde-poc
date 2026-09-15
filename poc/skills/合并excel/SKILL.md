---
name: 合并excel
description: 合并多个 Excel 文件到一个工作簿，支持数据清洗和去重
---

# Merge Excel Skill

## Description
批量合并多个 Excel 文件（.xlsx, .xls, .csv）到一个工作簿中。支持：
- 自动识别并合并同一目录下的所有 Excel 文件
- 可选合并到新的工作簿或追加到现有文件
- 自动跳过空文件和损坏文件
- 可配置数据去重、列对齐等处理

适用于数据处理、报表汇总、数据整合等场景。

## Trigger
当用户提到以下关键词时激活：
- 「合并 Excel」
- 「合并工作表」
- 「合并多个表格」
- 「把这几个 excel 合并在一起」
- 「汇总所有 excel」
- 文件路径 + 「合并」

## Instructions
1. 从用户输入中提取待合并的 Excel 文件路径或目录路径
2. 验证文件是否存在且为有效 Excel 格式
3. 读取所有 Excel 文件的结构和数据
4. 根据以下策略合并：
- 默认：将所有工作表追加到第一个工作簿
- 如文件列名一致，直接合并行
- 如列名不一致，自动对齐并补全空列
5. 检查并处理重复数据（可选）
6. 输出合并后的文件路径和内容概览
7. 如遇到错误，记录失败文件并跳过继续处理

## Tools Required
- file_system (文件读取和写入)
- code_interpreter (使用 Python pandas 处理 Excel)
- memory_store (存储处理过程和结果)

## Environment Variables
- MERGE_EXCEL_OUTPUT_DIR: 输出目录（默认当前目录 ./merged_output/）
- MERGE_EXCEL_MAX_FILES: 最大合并文件数（默认 100）
- MERGE_EXCEL_AUTO_DEDUPE: 是否自动去重（默认 true）

## Examples

### 示例 1：合并同一目录下的所有 Excel
**用户**：帮我合并 /data/sales/ 目录下的所有 Excel 文件
**返回**：
> ?? 开始合并 Excel 文件...
> 
> ?? 检测到 5 个 Excel 文件：
> - sales_2024_Q1.xlsx
> - sales_2024_Q2.xlsx
> - sales_2024_Q3.xlsx
> - sales_2024_Q4.xlsx
> - summary.xlsx
> 
> ? 合并成功！
> ?? 输出文件：./merged_output/merged_sales_2024.xlsx
> ?? 共合并 5 个工作表，总计 12,845 行数据
> ?? 跳过 1 个空文件：empty.xlsx
> 
> ?? 文件位置：./merged_output/merged_sales_2024.xlsx

### 示例 2：合并指定多个文件
**用户**：合并 report_a.xlsx 和 report_b.xlsx 和 report_c.xlsx
**返回**：
> ?? 开始合并 Excel 文件...
> 
> ? 已合并 3 个文件：
> - report_a.xlsx (3,240 行)
> - report_b.xlsx (4,580 行)
> - report_c.xlsx (2,150 行)
> 
> ?? 输出文件：./merged_output/merged_report.xlsx
> ?? 总计：9,970 行数据
> ?? 数据去重后：9,845 行（去重 125 行）

### 示例 3：错误处理 - 文件不存在
**用户**：合并 missing.xlsx 和 found.xlsx
**返回**：
> ?? 部分文件不存在或无法访问：
> ? missing.xlsx - 文件不存在
> 
> ? 已合并：found.xlsx
> ?? 输出文件：./merged_output/merged_partial.xlsx
> 
> ?? 提示：请检查文件路径是否正确

### 示例 4：错误处理 - 文件格式不支持
**用户**：合并 data.txt 和 data.xlsx
**返回**：
> ?? 文件格式不支持：
> ? data.txt - 非 Excel 格式，已跳过
> 
> ? 已处理：data.xlsx
> ?? 合并完成（仅 1 个文件）
> ?? 输出文件：./merged_output/merged_partial.xlsx

### 示例 5：列不对齐处理
**用户**：合并 order_a.xlsx 和 order_b.xlsx
**返回**：
> ?? 检测到列名不完全一致：
> - order_a.xlsx: [订单号，产品，数量，价格]
> - order_b.xlsx: [订单号，产品，数量，价格，备注]
> 
> ? 已自动对齐并合并：
> ?? 合并后共 5 列
> ?? 输出文件：./merged_output/merged_orders.xlsx 
