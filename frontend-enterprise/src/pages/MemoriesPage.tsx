import { DatabaseOutlined, SearchOutlined } from '@ant-design/icons';
import { Button, Card, Form, Input, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { api, TENANT_ID } from '../api/client';
import type { MemoryRead } from '../types';

type MemoryFilter = {
  username?: string;
  user_id?: string;
  q?: string;
};

export default function MemoriesPage() {
  const [rows, setRows] = useState<MemoryRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<MemoryFilter>();

  const load = async () => {
    setLoading(true);
    try {
      const values = form.getFieldsValue();
      const params = new URLSearchParams({ tenant_id: TENANT_ID });
      if (values.username?.trim()) params.set('username', values.username.trim());
      if (values.user_id?.trim()) params.set('user_id', values.user_id.trim());
      if (values.q?.trim()) params.set('q', values.q.trim());
      const result = await api.get<MemoryRead[]>(`/api/enterprise/memories?${params.toString()}`);
      setRows(result);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '查询失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const columns: ColumnsType<MemoryRead> = [
    { title: '用户名', dataIndex: 'username', width: 140, ellipsis: true, render: (value) => value || '-' },
    { title: '用户 ID', dataIndex: 'user_id', width: 180, ellipsis: true },
    { title: '类型', dataIndex: 'kind', width: 110, render: (value) => <Tag color={value === 'profile' ? 'green' : 'blue'}>{value}</Tag> },
    { title: '内容', dataIndex: 'content', ellipsis: true },
    { title: '会话', dataIndex: 'session_id', width: 180, ellipsis: true, render: (value) => value || '-' },
    { title: '更新', dataIndex: 'updated_at', width: 180, render: (value) => new Date(value).toLocaleString() },
  ];

  return (
    <>
      <div className="page-title">
        <Typography.Title level={3}>Memory 查询</Typography.Title>
      </div>
      <Card className="data-card" title={<><DatabaseOutlined /> 用户记忆</>}>
        <Form form={form} layout="inline" className="toolbar-form" onFinish={load}>
          <Form.Item name="username" label="用户名">
            <Input allowClear placeholder="如 user_demo" />
          </Form.Item>
          <Form.Item name="user_id" label="用户 ID">
            <Input allowClear placeholder="如 user_demo" />
          </Form.Item>
          <Form.Item name="q" label="关键词">
            <Input allowClear placeholder="姓名、订单、偏好" />
          </Form.Item>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} htmlType="submit" loading={loading}>查询</Button>
            <Button onClick={() => { form.resetFields(); load(); }}>重置</Button>
          </Space>
        </Form>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={loading}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 980 }}
        />
      </Card>
    </>
  );
}
