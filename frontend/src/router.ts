import { createRouter, createWebHistory } from "vue-router";
import { authState, loadSession } from "./auth";
import AdminView from "./views/AdminView.vue";
import LoginView from "./views/LoginView.vue";
import UserView from "./views/UserView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/user" },
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/user", component: UserView, meta: { role: "user" } },
    { path: "/admin", component: AdminView, meta: { role: "admin" } },
    { path: "/:pathMatch(.*)*", redirect: "/" }
  ]
});

router.beforeEach(async (to) => {
  if (to.meta.public) {
    await loadSession();
    if (authState.me) {
      return authState.me.user.role === "admin" ? "/admin" : "/user";
    }
    return true;
  }

  const me = await loadSession();
  if (!me) return { path: "/login", query: { next: to.fullPath } };
  if (to.meta.role === "admin" && me.user.role !== "admin") return "/user";
  if (to.path === "/user" && me.user.role === "admin") return "/admin";
  return true;
});

