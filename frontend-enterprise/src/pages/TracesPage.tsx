import { ReloadOutlined } from '@ant-design/icons';
import { Button, Card, Drawer, Table, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { api, TENANT_ID } from '../api/client';
import type { TraceSummary } from '../types';

export default function TracesPage() {
  const [rows, setRows] = useState<TraceSummary[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);

  const load = () =>
    api
      .get<TraceSummary[]>(`/api/enterprise/traces?tenant_id=${TENANT_ID}`)
      .then(setRows)
      .catch((error) => message.error(error.message));

  useEffect(() => {
    load();
  }, []);

  async function openDetail(row: TraceSummary) {
    const result = await api.get<Record<string, unknown>>(`/api/enterprise/traces/${row.session_id}?tenant_id=${TENANT_ID}`);
    setDetail(result);
  }

  const columns: ColumnsType<TraceSummary> = [
    { title: '会话 ID', dataIndex: 'session_id', width: 230, ellipsis: true },
    { title: '用户 ID', dataIndex: 'user_id', width: 150, ellipsis: true },
    { title: '当前技能', dataIndex: 'active_skill_id', width: 190, ellipsis: true },
    { title: '当前 Step', dataIndex: 'active_step_id', width: 190, ellipsis: true },
    { title: '工具调用', dataIndex: 'tool_call_count', width: 96 },
    { title: '状态', dataIndex: 'status', width: 96 },
    { title: '更新时间', dataIndex: 'updated_at', width: 210 },
    { title: '操作', width: 96, render: (_, row) => <Button size="small" onClick={() => openDetail(row)}>查看</Button> },
  ];

  return (
    <>
      <div className="page-title">
        <Typography.Title level={3}>Trace</Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
      </div>
      <Card className="data-card" title="会话 Trace">
        <Table
          rowKey="session_id"
          columns={columns}
          dataSource={rows}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1308 }}
          size="middle"
        />
      </Card>
      <Drawer title="Trace Detail" open={Boolean(detail)} width={720} onClose={() => setDetail(null)}>
        <pre>{JSON.stringify(detail, null, 2)}</pre>
      </Drawer>
    </>
  );
}
