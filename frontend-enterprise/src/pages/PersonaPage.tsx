import { SaveOutlined, UserOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Form, Input, Switch, Typography, message } from 'antd';
import { useEffect, useState } from 'react';
import { api, TENANT_ID } from '../api/client';
import type { PersonaRead, UIConfigRead } from '../types';

export default function PersonaPage() {
  const [form] = Form.useForm();
  const [uiForm] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [uiLoading, setUiLoading] = useState(false);
  const [updatedAt, setUpdatedAt] = useState('');
  const [uiUpdatedAt, setUiUpdatedAt] = useState('');

  useEffect(() => {
    api
      .get<PersonaRead>(`/api/enterprise/persona?tenant_id=${TENANT_ID}`)
      .then((row) => {
        form.setFieldsValue({ system_prompt: row.system_prompt });
        setUpdatedAt(row.updated_at);
      })
      .catch((error) => message.error(error.message));
    api
      .get<UIConfigRead>(`/api/enterprise/ui-config?tenant_id=${TENANT_ID}`)
      .then((row) => {
        uiForm.setFieldsValue(row);
        setUiUpdatedAt(row.updated_at);
      })
      .catch((error) => message.error(error.message));
  }, [form, uiForm]);

  async function save() {
    setLoading(true);
    try {
      const values = await form.validateFields();
      const row = await api.put<PersonaRead>('/api/enterprise/persona', {
        tenant_id: TENANT_ID,
        system_prompt: values.system_prompt,
      });
      setUpdatedAt(row.updated_at);
      message.success('人设已保存');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败');
    } finally {
      setLoading(false);
    }
  }

  async function saveUiConfig() {
    setUiLoading(true);
    try {
      const values = await uiForm.validateFields();
      const row = await api.put<UIConfigRead>('/api/enterprise/ui-config', {
        tenant_id: TENANT_ID,
        show_thinking_trace: values.show_thinking_trace,
        show_skill_trace: values.show_skill_trace,
        show_tool_trace: values.show_tool_trace,
      });
      setUiUpdatedAt(row.updated_at);
      message.success('展示设置已保存');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败');
    } finally {
      setUiLoading(false);
    }
  }

  return (
    <>
      <div className="page-title">
        <Typography.Title level={3}>人设</Typography.Title>
        <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={save}>保存</Button>
      </div>
      <Card className="editor-card" title={<><UserOutlined /> System Prompt</>}>
        <Alert
          type="info"
          showIcon
          message="这里配置的是租户级人设，会作为回复生成阶段的 system prompt 注入模型。"
          style={{ marginBottom: 16 }}
        />
        <Form form={form} layout="vertical">
          <Form.Item name="system_prompt" label="人设 Prompt" rules={[{ required: true }]}>
            <Input.TextArea className="persona-editor" rows={12} />
          </Form.Item>
        </Form>
        {updatedAt && <Typography.Text type="secondary">最后更新：{updatedAt}</Typography.Text>}
      </Card>
      <Card className="editor-card settings-card" title="用户端展示设置">
        <Alert
          type="info"
          showIcon
          message="这里控制用户端聊天中是否展示处理轨迹。Memory 只用于内部召回和总结，不会外显给用户。"
          style={{ marginBottom: 16 }}
        />
        <Form
          form={uiForm}
          layout="vertical"
          initialValues={{ show_thinking_trace: true, show_skill_trace: true, show_tool_trace: true }}
        >
          <Form.Item
            name="show_thinking_trace"
            label="展示思考状态"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Form.Item
            name="show_skill_trace"
            label="展示执行技能"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Form.Item
            name="show_tool_trace"
            label="展示工具调用"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
          <Button type="primary" icon={<SaveOutlined />} loading={uiLoading} onClick={saveUiConfig}>
            保存展示设置
          </Button>
        </Form>
        {uiUpdatedAt && <Typography.Text type="secondary">最后更新：{uiUpdatedAt}</Typography.Text>}
      </Card>
    </>
  );
}
