import {
  CheckOutlined,
  CloseOutlined,
  CopyOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  FileAddOutlined,
  FileSearchOutlined,
  InboxOutlined,
  ReloadOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Button, Card, Col, Collapse, Empty, Input, Progress, Row, Select, Space, Table, Tag, Typography, Upload, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, TENANT_ID } from '../api/client';
import type {
  KnowledgeBaseRead,
  KnowledgeBucketRead,
  KnowledgeDiscoveryRead,
  KnowledgeDocumentRead,
  KnowledgeIngestJobRead,
} from '../types';

const { Dragger } = Upload;
const ENTERPRISE_AGENT_STORAGE_KEY = 'ultrarag_enterprise_agent_scope';
const DEMO_KNOWLEDGE_BASE_NAME = 'Demo 会员权益与配送知识库';
const DEMO_KNOWLEDGE_FILENAME = 'knowledge_demo_membership_delivery.md';
const DEMO_KNOWLEDGE_MARKDOWN = `# 会员权益补偿与配送改派处理备忘

这份文档给客服和运营同学做处理参考。用户可能不会按固定格式描述问题，常见说法包括“黑卡券没到账”“活动赠品少了”“说好今天到但物流没动”“地址临时要改”“我不要退款，先补权益”等。

先判断用户当前到底要处理哪一类事情：
- 会员权益、券、积分、赠品、等级权益发放异常，走权益核对与补偿。
- 配送承诺、地址改派、期望送达时间变化，走仓配改派评估。
- 用户同时提到权益和配送时，先确认会影响当前履约的部分，再把另一件事保留为后续任务。
- 用户只是在问规则或口径时，先查知识依据，不要直接承诺补偿。

## 会员权益核对

如果用户说权益没到账、少发、补券、黑卡礼、积分、赠品等，需要先把用户身份和订单确认清楚。可以用用户 ID、订单号、会员等级、权益类型和活动批次去查一遍权益差异。

可参考的核对入口是 POST http://127.0.0.1:8000/api/mock/member/benefit-reconcile。

请求参数：
user_id：用户 ID 或会员身份标识，必填。
order_id：订单号，必填。
member_level：会员等级，可选，例如 normal、gold、black。
benefit_type：权益类型，可选，例如 coupon、points、gift。
benefit_campaign_id：活动批次，可选。

可以先按这个样例核对：用户 user_demo，订单 A12345，会员等级 black，权益类型 coupon，活动批次 vip_2026_midyear。实际处理时，从用户当前消息、历史会话和记忆里拼请求字段。

返回结果里重点看：found、eligible、expected_benefits、delivered_benefits、missing_benefits、difference_reason、recommended_action、can_auto_compensate。只要能说明差异和下一步即可，不要把所有字段都机械复述给用户。

若 can_auto_compensate 为 true，可以告诉用户会进入补发或补偿；若 false，要说明需要复核或转人工。若 found 为 false，先核对订单号和用户身份，不要编造权益。

## 配送改派评估

用户要求改地址、改时间、提前送、晚点送、指定配送方式，或者说承诺没兑现时，需要评估是否可以改派。这个动作不等于直接改派，先判断可行性和风险。

可参考的评估入口是 POST http://127.0.0.1:8000/api/mock/fulfillment/reroute-plan。

请求参数大致包括：
order_id：订单号，必填。
address：新的收货地址或地址片段。
expected_delivery_time：用户希望送达的时间。
delivery_priority：配送优先级，可选，例如 normal、urgent。
package_type：包裹类型，可选，例如 standard、fresh、fragile。

样例：订单 A12345，地址“上海市浦东新区测试路 88 号”，希望 2026-06-18 18:00 前送达，优先级 urgent，包裹 standard。实际处理时也要从当前会话中抽字段，不要照抄样例。

返回后看是否 can_reroute、plan_id、risk_level、estimated_delivery_window、extra_cost、recommended_action。如果无法改派，给出原因和替代建议；如果可改派，先向用户确认会产生的变化，不要直接替用户提交。

## 补偿与闭环

权益补偿或配送改派都会影响用户预期。回复时保持三件事：
1. 已确认的信息是什么。
2. 系统核对或评估后的结果是什么。
3. 下一步需要用户确认、等待复核，还是可以继续执行。

如果用户同时提出多个诉求，不要把所有诉求挤成一个步骤。先处理当前最阻塞的事项，把另一个事项作为后续任务。`;

export default function KnowledgeManagePage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<KnowledgeDocumentRead[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseRead[]>([]);
  const [discoveries, setDiscoveries] = useState<KnowledgeDiscoveryRead[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<KnowledgeDocumentRead | null>(null);
  const [buckets, setBuckets] = useState<KnowledgeBucketRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [agentId, setAgentId] = useState(() => window.localStorage.getItem(ENTERPRISE_AGENT_STORAGE_KEY) || '');

  const actionableDiscoveries = discoveries.filter((item) => item.status === 'pending' && item.suggestion_type !== 'warning');
  const warningDiscoveries = discoveries.filter((item) => item.suggestion_type === 'warning' || item.status !== 'pending');

  useEffect(() => {
    void refresh();
  }, [agentId]);

  useEffect(() => {
    const onScopeChange = (event: Event) => {
      setAgentId((event as CustomEvent<{ agentId?: string }>).detail?.agentId || window.localStorage.getItem(ENTERPRISE_AGENT_STORAGE_KEY) || '');
    };
    window.addEventListener('ultrarag-enterprise-agent-scope-change', onScopeChange);
    return () => window.removeEventListener('ultrarag-enterprise-agent-scope-change', onScopeChange);
  }, []);

  async function refresh() {
    setLoading(true);
    const suffix = agentId ? `&agent_id=${encodeURIComponent(agentId)}` : '';
    try {
      const [docRows, discoveryRows, kbRows] = await Promise.all([
        api.get<KnowledgeDocumentRead[]>(`/api/enterprise/knowledge/documents?tenant_id=${TENANT_ID}${suffix}`),
        api.get<KnowledgeDiscoveryRead[]>(`/api/enterprise/knowledge/discoveries?tenant_id=${TENANT_ID}${suffix}`),
        api.get<KnowledgeBaseRead[]>(`/api/enterprise/knowledge-bases?tenant_id=${TENANT_ID}${suffix}`),
      ]);
      setDocuments(docRows);
      setDiscoveries(discoveryRows);
      setKnowledgeBases(kbRows);
      const current = selectedDocument ? docRows.find((item) => item.id === selectedDocument.id) || null : docRows[0] || null;
      setSelectedDocument(current);
      if (current) {
        await loadBuckets(current, false);
      } else {
        setBuckets([]);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '刷新知识库失败');
    } finally {
      setLoading(false);
    }
  }

  async function loadBuckets(document: KnowledgeDocumentRead, select = true) {
    if (select) setSelectedDocument(document);
    try {
      const rows = await api.get<KnowledgeBucketRead[]>(
        `/api/enterprise/knowledge/documents/${document.id}/buckets?tenant_id=${TENANT_ID}`,
      );
      setBuckets(rows);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载知识桶失败');
    }
  }

  async function confirmDiscovery(item: KnowledgeDiscoveryRead) {
    try {
      await api.post(`/api/enterprise/knowledge/discoveries/${item.id}/confirm?tenant_id=${TENANT_ID}`);
      message.success('已确认建议');
      await refresh();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '确认失败');
    }
  }

  async function rejectDiscovery(item: KnowledgeDiscoveryRead) {
    try {
      await api.post(`/api/enterprise/knowledge/discoveries/${item.id}/reject?tenant_id=${TENANT_ID}`);
      message.success('已拒绝建议');
      await refresh();
    } catch (error) {
      message.error(error instanceof Error ? error.message : '拒绝失败');
    }
  }

  const documentColumns: ColumnsType<KnowledgeDocumentRead> = [
    {
      title: '知识',
      dataIndex: 'title',
      render: (_value, row) => (
        <button type="button" className="knowledge-doc-link" onClick={() => void loadBuckets(row)}>
          <span>{row.title || row.filename}</span>
          <small>{row.filename}</small>
        </button>
      ),
    },
    { title: '格式', dataIndex: 'file_type', width: 92, render: (value) => <Tag>{value}</Tag> },
    { title: '状态', dataIndex: 'status', width: 104, render: (value) => statusTag(value) },
    { title: '桶', dataIndex: 'bucket_count', width: 72 },
    { title: '片段', dataIndex: 'chunk_count', width: 72 },
    { title: '更新', dataIndex: 'updated_at', width: 120, render: (value) => String(value).slice(0, 10) },
  ];

  return (
    <div className="knowledge-page knowledge-manage-page">
      <div className="knowledge-hero">
        <div>
          <Typography.Title level={3}>知识管理</Typography.Title>
          <Typography.Text type="secondary">查看已入库文档、分桶切片结果，以及待确认的技能和工具发现。</Typography.Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refresh()} loading={loading}>刷新</Button>
          <Button type="primary" icon={<FileAddOutlined />} onClick={() => navigate('/enterprise/knowledge/new')}>
            新增知识
          </Button>
        </Space>
      </div>

      <Row gutter={[18, 18]}>
        <Col xs={24}>
          <Card className="knowledge-card knowledge-card-solid" title="知识库">
            {knowledgeBases.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无知识库" />
            ) : (
              <div className="knowledge-base-grid">
                {knowledgeBases.map((item) => (
                  <div className="knowledge-base-card" key={item.id}>
                    <div>
                      <Typography.Text strong>{item.name}</Typography.Text>
                      <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }}>
                        {item.description || '未填写描述'}
                      </Typography.Paragraph>
                    </div>
                    <Space size={6} wrap>
                      {statusTag(item.status)}
                      {item.version && <Tag>v{item.version}</Tag>}
                      {item.branch_sync_state && <Tag color={item.branch_sync_state === 'diverged' ? 'gold' : 'green'}>
                        {item.branch_sync_state === 'diverged' ? '分支修改' : '已同步'}
                      </Tag>}
                      <Tag>{item.document_count} 文档</Tag>
                      <Tag>{item.bucket_count} 桶</Tag>
                      <Tag>{item.chunk_count} 片段</Tag>
                    </Space>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card className="knowledge-card knowledge-card-solid" title="现有知识" extra={<DatabaseOutlined />}>
            <Table
              rowKey="id"
              columns={documentColumns}
              dataSource={documents}
              loading={loading}
              pagination={{ pageSize: 8 }}
              rowClassName={(row) => (row.id === selectedDocument?.id ? 'knowledge-row-selected' : '')}
            />
          </Card>
        </Col>
        <Col xs={24} xl={10}>
          <Card
            className="knowledge-card knowledge-card-solid"
            title={selectedDocument ? `知识桶 · ${selectedDocument.title || selectedDocument.filename}` : '知识桶'}
            extra={<FileSearchOutlined />}
          >
            {!selectedDocument ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="选择一个文档查看知识桶" />
            ) : buckets.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无分桶结果" />
            ) : (
              <div className="knowledge-bucket-list">
                {buckets.map((bucket) => (
                  <div className="knowledge-bucket-item" key={bucket.id}>
                    <div className="knowledge-bucket-title">
                      <span>{bucket.title}</span>
                      {bucketStatusTag(bucket)}
                    </div>
                    <Typography.Paragraph ellipsis={{ rows: 3 }}>{bucket.summary}</Typography.Paragraph>
                    <div className="knowledge-bucket-meta">
                      <Tag>{bucket.bucket_key}</Tag>
                      <Tag>{bucket.chunk_count} 片段</Tag>
                      <Tag>{bucket.token_estimate} tokens</Tag>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Card className="knowledge-card knowledge-card-solid" title="自发现建议">
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={13}>
            <DiscoveryColumn
              title="可确认建议"
              description="模型从知识中发现的技能和工具草案。确认后才会进入系统。"
              items={actionableDiscoveries}
              onConfirm={confirmDiscovery}
              onReject={rejectDiscovery}
            />
          </Col>
          <Col xs={24} lg={11}>
            <DiscoveryColumn
              title="信息与警告"
              description="不满足入库条件、已处理或需要人工补充的信息。"
              items={warningDiscoveries}
              onConfirm={confirmDiscovery}
              onReject={rejectDiscovery}
              readonly
            />
          </Col>
        </Row>
      </Card>
    </div>
  );
}

export function KnowledgeAddPage() {
  const navigate = useNavigate();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseRead[]>([]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState('');
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState('');
  const [jobs, setJobs] = useState<Record<string, KnowledgeIngestJobRead>>({});
  const [agentId, setAgentId] = useState(() => window.localStorage.getItem(ENTERPRISE_AGENT_STORAGE_KEY) || '');
  const activeJobs = useMemo(
    () => Object.values(jobs).filter((job) => ['queued', 'running'].includes(job.status)),
    [jobs],
  );

  useEffect(() => {
    void refreshKnowledgeBases();
  }, [agentId]);

  useEffect(() => {
    const onScopeChange = (event: Event) => {
      setAgentId((event as CustomEvent<{ agentId?: string }>).detail?.agentId || window.localStorage.getItem(ENTERPRISE_AGENT_STORAGE_KEY) || '');
    };
    window.addEventListener('ultrarag-enterprise-agent-scope-change', onScopeChange);
    return () => window.removeEventListener('ultrarag-enterprise-agent-scope-change', onScopeChange);
  }, []);

  useEffect(() => {
    if (activeJobs.length === 0) return;
    const timer = window.setInterval(() => {
      activeJobs.forEach((job) => {
        void api
          .get<KnowledgeIngestJobRead>(`/api/enterprise/knowledge/jobs/${job.id}?tenant_id=${TENANT_ID}`)
          .then((next) => setJobs((prev) => ({ ...prev, [next.id]: next })))
          .catch(() => undefined);
      });
    }, 1400);
    return () => window.clearInterval(timer);
  }, [activeJobs]);

  async function refreshKnowledgeBases() {
    try {
      const suffix = agentId ? `&agent_id=${encodeURIComponent(agentId)}` : '';
      const rows = await api.get<KnowledgeBaseRead[]>(`/api/enterprise/knowledge-bases?tenant_id=${TENANT_ID}${suffix}`);
      setKnowledgeBases(rows);
      setSelectedKnowledgeBaseId((current) => current || rows.find((item) => item.status === 'active')?.id || rows[0]?.id || '');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载知识库失败');
    }
  }

  async function createKnowledgeBaseWithName(name: string, description = '') {
    if (!name) {
      message.warning('请先输入知识库名称');
      return null;
    }
    try {
      const query = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
      const row = await api.post<KnowledgeBaseRead>(`/api/enterprise/knowledge-bases${query}`, {
        tenant_id: TENANT_ID,
        name,
        description,
      });
      setKnowledgeBases((prev) => [row, ...prev]);
      setSelectedKnowledgeBaseId(row.id);
      return row;
    } catch (error) {
      message.error(error instanceof Error ? error.message : '创建知识库失败');
      return null;
    }
  }

  async function createKnowledgeBase() {
    const name = newKnowledgeBaseName.trim();
    const row = await createKnowledgeBaseWithName(name);
    if (row) {
      setNewKnowledgeBaseName('');
      message.success('已创建知识库');
    }
  }

  async function uploadFile(file: File, explicitKnowledgeBaseId?: string) {
    const targetKnowledgeBaseId = explicitKnowledgeBaseId || selectedKnowledgeBaseId;
    if (!targetKnowledgeBaseId) {
      message.warning('请先选择或创建知识库');
      return;
    }
    try {
      const contentBase64 = await fileToBase64(file);
      const suffix = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
      const job = await api.post<KnowledgeIngestJobRead>(`/api/enterprise/knowledge/documents${suffix}`, {
        tenant_id: TENANT_ID,
        knowledge_base_id: targetKnowledgeBaseId,
        filename: file.name,
        title: file.name.replace(/\.[^.]+$/, ''),
        content_base64: contentBase64,
      });
      setJobs((prev) => ({ ...prev, [job.id]: job }));
      message.success('已创建知识入库任务');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '上传失败');
    }
  }

  async function uploadDemoKnowledge() {
    let targetKnowledgeBaseId = selectedKnowledgeBaseId;
    if (!targetKnowledgeBaseId) {
      const existingDemoBase = knowledgeBases.find((item) => item.name === DEMO_KNOWLEDGE_BASE_NAME);
      if (existingDemoBase) {
        targetKnowledgeBaseId = existingDemoBase.id;
        setSelectedKnowledgeBaseId(existingDemoBase.id);
      } else {
        const row = await createKnowledgeBaseWithName(
          DEMO_KNOWLEDGE_BASE_NAME,
          '用于验证知识分桶、渐进检索、技能发现和工具发现的测试知识库。',
        );
        if (!row) return;
        targetKnowledgeBaseId = row.id;
      }
    }
    const demoFile = new File([DEMO_KNOWLEDGE_MARKDOWN], DEMO_KNOWLEDGE_FILENAME, { type: 'text/markdown;charset=utf-8' });
    await uploadFile(demoFile, targetKnowledgeBaseId);
  }

  async function copyDemoKnowledge() {
    try {
      await navigator.clipboard.writeText(DEMO_KNOWLEDGE_MARKDOWN);
      message.success('已复制 Demo 文档内容');
    } catch {
      message.error('复制失败，请直接使用上传 Demo');
    }
  }

  return (
    <div className="knowledge-page knowledge-add-page">
      <div className="knowledge-hero">
        <div>
          <Typography.Title level={3}>新增知识</Typography.Title>
          <Typography.Text type="secondary">上传业务文档，后台会完成解析、分桶、切片和自发现建议生成。</Typography.Text>
        </div>
        <Button icon={<RightOutlined />} onClick={() => navigate('/enterprise/knowledge')}>查看知识管理</Button>
      </div>

      <Card className="knowledge-card knowledge-upload-card">
        <div className="knowledge-upload-controls">
          <div>
            <Typography.Text strong>归属知识库</Typography.Text>
            <Typography.Text type="secondary">每个上传文档、知识桶和切片都会归属到这里。</Typography.Text>
          </div>
          <Space wrap>
            <Select
              className="knowledge-base-select"
              placeholder="选择知识库"
              value={selectedKnowledgeBaseId || undefined}
              onChange={setSelectedKnowledgeBaseId}
              options={knowledgeBases.map((item) => ({ value: item.id, label: item.name }))}
            />
            <Input
              className="knowledge-base-create-input"
              placeholder="新建知识库名称"
              value={newKnowledgeBaseName}
              onChange={(event) => setNewKnowledgeBaseName(event.target.value)}
              onPressEnter={() => void createKnowledgeBase()}
            />
            <Button onClick={() => void createKnowledgeBase()}>新建知识库</Button>
          </Space>
        </div>
        <div className="knowledge-demo-panel">
          <div className="knowledge-demo-copy">
            <ExperimentOutlined />
            <div>
              <Typography.Text strong>测试 Demo：会员权益补偿与配送改派</Typography.Text>
              <Typography.Text type="secondary">
                用于验证知识分桶、切片、自发现技能，以及从自然文档中抽取两个未配置工具。
              </Typography.Text>
            </div>
          </div>
          <Space wrap>
            <Button icon={<ExperimentOutlined />} onClick={() => void uploadDemoKnowledge()}>
              上传测试 Demo
            </Button>
            <Button icon={<CopyOutlined />} onClick={() => void copyDemoKnowledge()}>
              复制内容
            </Button>
          </Space>
        </div>
        <Dragger
          multiple
          showUploadList={false}
          beforeUpload={(file) => {
            void uploadFile(file);
            return false;
          }}
          accept=".doc,.docx,.txt,.md,.markdown,.html,.htm,.pdf"
        >
          <div className="knowledge-upload-inner">
            <InboxOutlined />
            <div>
              <strong>拖拽文档到这里，或点击选择文件</strong>
              <span>支持 doc/docx/txt/md/html/pdf；旧版 doc 会提示转换为 docx。</span>
            </div>
          </div>
        </Dragger>
      </Card>

      <Card className="knowledge-card knowledge-card-solid" title="入库任务">
        {Object.values(jobs).length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="上传后这里会显示解析和分桶进度" />
        ) : (
          <div className="knowledge-jobs">
            {Object.values(jobs).map((job) => (
              <div className="knowledge-job" key={job.id}>
                <div className="knowledge-job-head">
                  <div>
                    <Typography.Text strong>{job.filename}</Typography.Text>
                    <Typography.Text type="secondary"> · {job.stage}</Typography.Text>
                  </div>
                  {statusTag(job.status)}
                </div>
                <Progress percent={Math.round(job.progress * 100)} status={job.status === 'failed' ? 'exception' : undefined} />
                {job.error && <Typography.Text type="danger">{job.error}</Typography.Text>}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function DiscoveryColumn({
  title,
  description,
  items,
  readonly = false,
  onConfirm,
  onReject,
}: {
  title: string;
  description: string;
  items: KnowledgeDiscoveryRead[];
  readonly?: boolean;
  onConfirm: (item: KnowledgeDiscoveryRead) => Promise<void>;
  onReject: (item: KnowledgeDiscoveryRead) => Promise<void>;
}) {
  return (
    <div className="knowledge-discovery-column">
      <div className="knowledge-section-heading">
        <div>
          <strong>{title}</strong>
          <span>{description}</span>
        </div>
        <Tag>{items.length}</Tag>
      </div>
      {items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无内容" />
      ) : (
        <Space direction="vertical" size={12} className="knowledge-discovery-list">
          {items.map((item) => (
            <div className={`knowledge-discovery ${item.suggestion_type}`} key={item.id}>
              <div className="knowledge-discovery-header">
                <Space size={8} wrap>
                  <Typography.Text strong>{item.title}</Typography.Text>
                  <Tag>{typeLabel(item.suggestion_type)}</Tag>
                  {statusTag(item.status)}
                </Space>
                {!readonly && item.status === 'pending' && (
                  <Space size={8}>
                    <Button size="small" shape="circle" icon={<CheckOutlined />} onClick={() => void onConfirm(item)} />
                    <Button size="small" shape="circle" icon={<CloseOutlined />} onClick={() => void onReject(item)} />
                  </Space>
                )}
              </div>
              {item.reason && <Typography.Paragraph type="secondary">{item.reason}</Typography.Paragraph>}
              <Collapse
                ghost
                items={[
                  {
                    key: 'payload',
                    label: '查看详情',
                    children: <pre className="knowledge-json">{JSON.stringify(item.payload, null, 2)}</pre>,
                  },
                ]}
              />
            </div>
          ))}
        </Space>
      )}
    </div>
  );
}

function statusTag(status: string) {
  const color = status === 'succeeded' || status === 'ready' || status === 'confirmed' ? 'green' : status === 'failed' ? 'red' : 'gold';
  return <Tag color={color}>{status}</Tag>;
}

function bucketStatusTag(bucket: KnowledgeBucketRead) {
  if (bucket.status === 'ready') return <Tag color="green">达标</Tag>;
  return <Tag color="gold">待补足</Tag>;
}

function typeLabel(type: string) {
  if (type === 'skill') return '技能';
  if (type === 'tool') return '工具';
  return '提示';
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('读取文件失败'));
    reader.onload = () => {
      const result = String(reader.result || '');
      resolve(result.includes(',') ? result.split(',').pop() || '' : result);
    };
    reader.readAsDataURL(file);
  });
}
