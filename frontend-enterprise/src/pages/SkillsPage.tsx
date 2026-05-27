import { CheckCircleOutlined, CloudUploadOutlined, PlusOutlined, StopOutlined } from '@ant-design/icons';
import { Button, Card, Input, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { api, TENANT_ID } from '../api/client';
import type { SkillCard, SkillRead } from '../types';

const emptySkill: SkillCard = {
  skill_id: 'new_skill',
  name: '新技能',
  version: '1.0.0',
  business_domain: 'general',
  description: '',
  trigger_intents: [],
  user_utterance_examples: [],
  goal: [],
  required_info: [],
  steps: [],
  interruption_policy: {},
  response_rules: [],
};

type SkillCardEditor = Omit<SkillCard, 'skill_id'> & { skill_id: string };

function toSkillEditor(content: SkillCard): SkillCardEditor {
  const { skill_id, ...rest } = content;
  return { skill_id, ...rest };
}

function fromSkillEditor(content: SkillCardEditor | (Partial<SkillCardEditor> & Partial<SkillCard>)): SkillCard {
  const { skill_id, ...rest } = content;
  return { skill_id: skill_id || 'new_skill', ...rest } as SkillCard;
}

export default function SkillsPage() {
  const [rows, setRows] = useState<SkillRead[]>([]);
  const [selected, setSelected] = useState<SkillRead | null>(null);
  const [jsonText, setJsonText] = useState(JSON.stringify(toSkillEditor(emptySkill), null, 2));
  const [loading, setLoading] = useState(false);

  const load = () =>
    api
      .get<SkillRead[]>(`/api/enterprise/skills?tenant_id=${TENANT_ID}`)
      .then(setRows)
      .catch((error) => message.error(error.message));

  useEffect(() => {
    load();
  }, []);

  const columns: ColumnsType<SkillRead> = useMemo(
    () => [
      { title: '技能名称', dataIndex: 'name', width: 180, ellipsis: true },
      { title: '技能 ID', dataIndex: 'skill_id', width: 190, ellipsis: true },
      { title: '业务域', dataIndex: 'business_domain', width: 140, ellipsis: true },
      { title: '版本', dataIndex: 'version', width: 96 },
      {
        title: '状态',
        dataIndex: 'status',
        width: 116,
        render: (status) => <Tag color={status === 'published' ? 'green' : status === 'draft' ? 'blue' : 'default'}>{status}</Tag>,
      },
      {
        title: '操作',
        width: 210,
        render: (_, row) => (
          <span className="table-actions">
            <Button size="small" onClick={() => edit(row)}>编辑</Button>
            <Button size="small" icon={<CheckCircleOutlined />} onClick={() => publish(row)}>发布</Button>
            <Button size="small" icon={<StopOutlined />} onClick={() => archive(row)}>下线</Button>
          </span>
        ),
      },
    ],
    [],
  );

  function edit(row: SkillRead) {
    setSelected(row);
    setJsonText(JSON.stringify(toSkillEditor(row.content), null, 2));
  }

  function createNew() {
    setSelected(null);
    setJsonText(JSON.stringify(toSkillEditor({ ...emptySkill, skill_id: `skill_${Date.now()}` }), null, 2));
  }

  async function save() {
    setLoading(true);
    try {
      const content = fromSkillEditor(JSON.parse(jsonText));
      if (selected) {
        await api.put(`/api/enterprise/skills/${selected.skill_id}`, { tenant_id: TENANT_ID, content });
      } else {
        await api.post('/api/enterprise/skills', { tenant_id: TENANT_ID, content, status: 'draft' });
      }
      message.success('已保存');
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '保存失败');
    } finally {
      setLoading(false);
    }
  }

  async function publish(row: SkillRead) {
    await api.post(`/api/enterprise/skills/${row.skill_id}/publish?tenant_id=${TENANT_ID}`);
    message.success('已发布');
    load();
  }

  async function archive(row: SkillRead) {
    await api.post(`/api/enterprise/skills/${row.skill_id}/archive?tenant_id=${TENANT_ID}`);
    message.success('已下线');
    load();
  }

  return (
    <>
      <div className="page-title">
        <Typography.Title level={3}>技能管理</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={createNew}>新建</Button>
      </div>
      <div className="grid-2">
        <Card className="data-card" title="技能列表">
          <Table
            rowKey="id"
            columns={columns}
            dataSource={rows}
            pagination={{ pageSize: 8 }}
            scroll={{ x: 930 }}
            size="middle"
          />
        </Card>
        <Card
          className="editor-card"
          title={selected ? `编辑 ${selected.skill_id}` : '新建草稿'}
          extra={<Button type="primary" icon={<CloudUploadOutlined />} loading={loading} onClick={save}>保存</Button>}
        >
          <Input.TextArea className="json-editor" value={jsonText} onChange={(event) => setJsonText(event.target.value)} />
        </Card>
      </div>
    </>
  );
}
