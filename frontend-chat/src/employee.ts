import type { AgentProfileRead } from './types';
import type { AuthUser } from './api/client';

export type EmployeeProfile = {
  roleName: string;
  avatarText: string;
  avatarTone: string;
};

function stringFromMeta(metadata: Record<string, unknown> | undefined, key: string): string {
  const value = metadata?.[key];
  return typeof value === 'string' ? value : '';
}

export function employeeProfile(agent?: AgentProfileRead | null): EmployeeProfile {
  if (agent?.is_overall) {
    return { roleName: '开放广场平台', avatarText: '广', avatarTone: 'overall' };
  }
  return {
    roleName: stringFromMeta(agent?.metadata, 'role_name') || '在线客服员工',
    avatarText: stringFromMeta(agent?.metadata, 'avatar_text') || '员',
    avatarTone: stringFromMeta(agent?.metadata, 'avatar_tone') || 'teal',
  };
}

export function employeeDisplayName(agent?: AgentProfileRead | null): string {
  if (!agent) return '数字员工';
  if (agent.is_overall) return '开放广场平台';
  return (agent.name || '数字员工').replace(/智能体/g, '员工');
}

export function isGalleryEmployee(agent?: AgentProfileRead | null): boolean {
  return agent?.metadata?.published_to_gallery === true;
}

export function isEmployeeOwnedBy(agent: AgentProfileRead, user?: AuthUser | null): boolean {
  if (!user) return false;
  const ownerUserId = agent.metadata?.owner_user_id;
  const ownerUsername = agent.metadata?.owner_username;
  return ownerUserId === user.id || ownerUsername === user.username;
}

export function visibleChatEmployees(rows: AgentProfileRead[], user?: AuthUser | null): AgentProfileRead[] {
  return rows.filter((agent) => (
    !agent.is_overall && (isEmployeeOwnedBy(agent, user) || isGalleryEmployee(agent))
  ));
}
