import {
  DeleteOutlined,
  MoreOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { Button, Card, Dropdown, Modal, Space, Table, Tag, Typography, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { api, TENANT_ID } from '../api/client';
import type { AgentProfileRead, AgentResourceBindingRead } from '../types';

const ENTERPRISE_AGENT_STORAGE_KEY = 'ultrarag_enterprise_agent_scope';

const RESOURCE_LABELS: Record<string, string> = {
  skill: '技能',
  general_skill: '通用技能',
  knowledge_base: '知识库',
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentProfileRead[]>([]);
  const [loading, setLoading] = useState(false);
  const selectedAgentId = window.localStorage.getItem(ENTERPRISE_AGENT_STORAGE_KEY) || '';
  const currentAgent = agents.find((item) => item.id === selectedAgentId);

  async function load() {
    setLoading(true);
    try {
      const rows = await api.get<AgentProfileRead[]>(`/api/enterprise/agents?tenant_id=${TENANT_ID}`);
      setAgents(rows);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载智能体失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const overallAgent = agents.find((item) => item.is_overall);
  const branchAgents = useMemo(() => agents.filter((item) => !item.is_overall), [agents]);

  if (currentAgent && !currentAgent.is_overall) {
    return <Navigate to="/enterprise/dashboard" replace />;
  }

  async function updateStatus(row: AgentProfileRead, status: 'active' | 'archived') {
    try {
      await api.put<AgentProfileRead>(`/api/enterprise/agents/${row.id}`, {
        tenant_id: TENANT_ID,
        status,
      });
      message.success(status === 'active' ? '已上线智能体' : '已下线智能体');
      await load();
      window.dispatchEvent(new Event('ultrarag-enterprise-agent-scope-refresh'));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '更新智能体失败');
    }
  }

  function deleteAgent(row: AgentProfileRead) {
    Modal.confirm({
      title: `删除智能体「${row.name}」？`,
      content: '删除后会移除该分支智能体的资源绑定和分支配置；整体资源池不受影响。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      async onOk() {
        try {
          await api.delete(`/api/enterprise/agents/${row.id}?tenant_id=${TENANT_ID}`);
          if (window.localStorage.getItem(ENTERPRISE_AGENT_STORAGE_KEY) === row.id && overallAgent) {
            window.localStorage.setItem(ENTERPRISE_AGENT_STORAGE_KEY, overallAgent.id);
            window.dispatchEvent(
              new CustomEvent('ultrarag-enterprise-agent-scope-change', { detail: { agentId: overallAgent.id } }),
            );
          }
          message.success('已删除智能体');
          await load();
          window.dispatchEvent(new Event('ultrarag-enterprise-agent-scope-refresh'));
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除智能体失败');
        }
      },
    });
  }

  const columns: ColumnsType<AgentProfileRead> = [
    {
      title: '智能体',
      dataIndex: 'name',
      render: (_, row) => (
        <div className="agent-name-cell">
          <span className="agent-name-icon"><RobotOutlined /></span>
          <span>
            <Typography.Text strong>{row.name}</Typography.Text>
            <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }}>
              {row.description || '未填写描述'}
            </Typography.Paragraph>
          </span>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'default'}>{status === 'active' ? '已上线' : '已下线'}</Tag>
      ),
    },
    {
      title: '可见资源',
      dataIndex: 'resources',
      render: (resources: AgentResourceBindingRead[]) => <ResourceSummary resources={resources || []} />,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      width: 130,
      render: (value: string) => value?.slice(0, 10) || '-',
    },
    {
      title: '操作',
      width: 82,
      fixed: 'right',
      render: (_, row) => (
        <Dropdown
          trigger={['click']}
          menu={{
            items: [
              row.status === 'active'
                ? { key: 'archive', icon: <PauseCircleOutlined />, label: '下线' }
                : { key: 'active', icon: <PlayCircleOutlined />, label: '上线' },
              { key: 'delete', icon: <DeleteOutlined />, label: '删除', danger: true },
            ],
            onClick: ({ key }) => {
              if (key === 'active') void updateStatus(row, 'active');
              if (key === 'archive') void updateStatus(row, 'archived');
              if (key === 'delete') deleteAgent(row);
            },
          }}
        >
          <Button type="text" icon={<MoreOutlined />} aria-label="智能体操作" />
        </Dropdown>
      ),
    },
  ];

  return (
    <div className="page agents-page">
      <div className="page-title">
        <div>
          <Typography.Title level={2}>智能体</Typography.Title>
          <Typography.Paragraph type="secondary">管理整体资源池下的分支智能体，上线、下线或删除分支。</Typography.Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>
          刷新
        </Button>
      </div>

      <div className="agents-summary-grid">
        <Card className="agent-summary-card">
          <span>整体智能体</span>
          <strong>{overallAgent?.name || '-'}</strong>
          <small>主干资源池，不可删除</small>
        </Card>
        <Card className="agent-summary-card">
          <span>分支总数</span>
          <strong>{branchAgents.length}</strong>
          <small>{branchAgents.filter((item) => item.status === 'active').length} 个已上线</small>
        </Card>
        <Card className="agent-summary-card">
          <span>已下线</span>
          <strong>{branchAgents.filter((item) => item.status !== 'active').length}</strong>
          <small>下线后 Chat 端不可选择</small>
        </Card>
      </div>

      <Card className="data-card agent-table-card" title="分支智能体">
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={branchAgents}
          pagination={{ pageSize: 10, showSizeChanger: false }}
          scroll={{ x: 920 }}
        />
      </Card>
    </div>
  );
}

function ResourceSummary({ resources }: { resources: AgentResourceBindingRead[] }) {
  const counts = resources.reduce<Record<string, { active: number; inactive: number; deleted: number }>>((acc, item) => {
    const bucket = acc[item.resource_type] || { active: 0, inactive: 0, deleted: 0 };
    if (item.status === 'deleted') bucket.deleted += 1;
    else if (item.status === 'active') bucket.active += 1;
    else bucket.inactive += 1;
    acc[item.resource_type] = bucket;
    return acc;
  }, {});

  if (!resources.length) {
    return <Typography.Text type="secondary">暂无绑定资源</Typography.Text>;
  }

  return (
    <Space size={[6, 6]} wrap>
      {Object.entries(counts).map(([type, count]) => (
        <Tag className="agent-resource-tag" key={type}>
          {RESOURCE_LABELS[type] || type}
          <span>{count.active}</span>
          {count.inactive > 0 && <small>下线 {count.inactive}</small>}
          {count.deleted > 0 && <small>隐藏 {count.deleted}</small>}
        </Tag>
      ))}
    </Space>
  );
}
