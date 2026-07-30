import { reactive } from "vue";
import type { Me, Role } from "./types";
import { ApiError, devLogin, getMe, logout as apiLogout } from "./api";

interface AuthState {
  me: Me | null;
  checked: boolean;
}

export const authState = reactive<AuthState>({
  me: null,
  checked: false
});

export async function loadSession(force = false): Promise<Me | null> {
  if (authState.checked && !force) return authState.me;
  try {
    authState.me = await getMe();
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    authState.me = null;
  } finally {
    authState.checked = true;
  }
  return authState.me;
}

export async function loginForDevelopment(role: Role): Promise<Me> {
  authState.me = await devLogin(role);
  authState.checked = true;
  return authState.me;
}

export async function logout(): Promise<void> {
  await apiLogout();
  authState.me = null;
  authState.checked = true;
}

