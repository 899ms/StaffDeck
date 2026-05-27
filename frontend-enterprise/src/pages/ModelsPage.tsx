import { ApiOutlined, CheckOutlined, ExperimentOutlined, SaveOutlined } from '@ant-design/icons';
import { Button, Card, Form, Input, InputNumber, Switch, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { api, TENANT_ID } from '../api/client';
import type { ModelConfigRead } from '../types';

export default function ModelsPage() {
  const [rows, setRows] = useState<ModelConfigRead[]>([]);
  const [selected, setSelected] = useState<ModelConfigRead | null>(null);
  const [form] = Form.useForm();

  const load = () =>
    api
      .get<ModelConfigRead[]>(`/api/enterprise/model-configs?tenant_id=${TENANT_ID}`)
      .then(setRows)
      .catch((error) => message.error(error.message));

  useEffect(() => {
    load();
  }, []);

  function edit(row: ModelConfigRead) {
    setSelected(row);
    form.setFieldsValue({ ...row, api_key: '' });
  }

  async function save() {
    const values = await form.validateFields();
    const payload = { ...values, tenant_id: TENANT_ID, api_key: values.api_key || undefined };
    if (selected) {
      await api.put(`/api/enterprise/model-configs/${selected.id}`, payload);
    } else {
      await api.post('/api/enterprise/model-configs', payload);
    }
    message.success('已保存');
    setSelected(null);
    form.resetFields();
    load();
  }

  async function setDefault(row: ModelConfigRead) {
    await api.post(`/api/enterprise/model-configs/${row.id}/set-default?tenant_id=${TENANT_ID}`);
    message.success('已设为默认');
    load();
  }

  async function test(row: ModelConfigRead) {
    const result = await api.post<{ success: boolean; message: string; output?: string }>(
      `/api/enterprise/model-configs/${row.id}/test?tenant_id=${TENANT_ID}`,
    );
    result.success ? message.success(result.output || result.message) : message.error(result.message);
  }

  const columns: ColumnsType<ModelConfigRead> = [
    { title: '名称', dataIndex: 'name', width: 150, ellipsis: true },
    { title: '模型', dataIndex: 'model', width: 180, ellipsis: true },
    { title: 'Base URL', dataIndex: 'base_url', width: 240, ellipsis: true },
    {
      title: 'API Key',
      dataIndex: 'api_key_masked',
      width: 180,
      render: (value) => <span className="code-cell">{value || '-'}</span>,
    },
    { title: '默认', render: (_, row) => (row.is_default ? <Tag color="green">default</Tag> : null), width: 90 },
    {
      title: '操作',
      width: 230,
      render: (_, row) => (
        <span className="table-actions">
          <Button size="small" onClick={() => edit(row)}>编辑</Button>
          <Button size="small" icon={<CheckOutlined />} onClick={() => setDefault(row)}>默认</Button>
          <Button size="small" icon={<ExperimentOutlined />} onClick={() => test(row)}>测试</Button>
        </span>
      ),
    },
  ];

  return (
    <>
      <div className="page-title">
        <Typography.Title level={3}>模型配置</Typography.Title>
      </div>
      <div className="grid-2">
        <Card className="data-card" title="模型列表">
          <Table
            rowKey="id"
            columns={columns}
            dataSource={rows}
            pagination={{ pageSize: 8 }}
            scroll={{ x: 1070 }}
            size="middle"
          />
        </Card>
        <Card className="editor-card" title={selected ? '编辑模型' : '新建模型'}>
          <Form form={form} layout="vertical" initialValues={{ provider: 'openai_compatible', temperature: 0.2, max_output_tokens: 2048, enabled: true }}>
            <Form.Item name="name" label="配置名称" rules={[{ required: true }]}><Input prefix={<ApiOutlined />} /></Form.Item>
            <Form.Item name="provider" label="Provider" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="base_url" label="Base URL"><Input /></Form.Item>
            <Form.Item name="api_key" label="API Key"><Input.Password placeholder={selected ? '留空则保持原值' : undefined} /></Form.Item>
            <Form.Item name="model" label="Model" rules={[{ required: true }]}><Input /></Form.Item>
            <div className="form-number-row">
              <Form.Item name="temperature" label="Temperature"><InputNumber min={0} max={2} step={0.1} /></Form.Item>
              <Form.Item name="max_output_tokens" label="Max Tokens"><InputNumber min={128} max={32000} /></Form.Item>
            </div>
            <Form.Item name="is_default" label="设为默认" valuePropName="checked"><Switch /></Form.Item>
            <Form.Item name="enabled" label="启用" valuePropName="checked"><Switch /></Form.Item>
            <div className="form-actions">
              <Button type="primary" icon={<SaveOutlined />} onClick={save}>保存</Button>
              <Button onClick={() => { setSelected(null); form.resetFields(); }}>清空</Button>
            </div>
          </Form>
        </Card>
      </div>
    </>
  );
}
