import { SendOutlined } from '@ant-design/icons';
import { Button, Card, Collapse, Input, Space, Typography, message } from 'antd';
import { useState } from 'react';
import { api, TENANT_ID } from '../api/client';
import type { ChatTurnResponse } from '../types';

type ChatMessage = { role: 'user' | 'assistant'; content: string };

export default function DebugPage() {
  const [sessionId, setSessionId] = useState('');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastTurn, setLastTurn] = useState<ChatTurnResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input.trim()) return;
    const userText = input;
    setInput('');
    setMessages((items) => [...items, { role: 'user', content: userText }]);
    setLoading(true);
    try {
      const result = await api.post<ChatTurnResponse>('/api/chat/turn', {
        tenant_id: TENANT_ID,
        session_id: sessionId || undefined,
        user_id: 'enterprise_debugger',
        message: userText,
        channel: 'enterprise_debug',
        debug: true,
      });
      setSessionId(result.session_id);
      setLastTurn(result);
      setMessages((items) => [...items, { role: 'assistant', content: result.reply }]);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '发送失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="page-title">
        <Typography.Title level={3}>Agent 调试</Typography.Title>
        <Input
          className="page-field"
          value={sessionId}
          onChange={(event) => setSessionId(event.target.value)}
          placeholder="Session ID"
        />
      </div>
      <div className="grid-2">
        <Card>
          <div className="chat-panel">
            <div className="messages">
              {messages.map((item, index) => (
                <div key={`${item.role}-${index}`} className={`message-row ${item.role}`}>
                  <div className="bubble">{item.content}</div>
                </div>
              ))}
            </div>
            <Space.Compact>
              <Input value={input} onChange={(event) => setInput(event.target.value)} onPressEnter={send} placeholder="输入调试消息" />
              <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={send}>发送</Button>
            </Space.Compact>
          </div>
        </Card>
        <Card title="Trace Snapshot">
          <Collapse
            defaultActiveKey={['router', 'session']}
            items={[
              { key: 'router', label: 'Router Decision', children: <pre>{JSON.stringify(lastTurn?.router_decision, null, 2)}</pre> },
              { key: 'step', label: 'Step Agent', children: <pre>{JSON.stringify(lastTurn?.step_result, null, 2)}</pre> },
              { key: 'tool', label: 'Tool Result', children: <pre>{JSON.stringify(lastTurn?.tool_result, null, 2)}</pre> },
              { key: 'session', label: 'Session State', children: <pre>{JSON.stringify(lastTurn?.session_state, null, 2)}</pre> },
            ]}
          />
        </Card>
      </div>
    </>
  );
}
