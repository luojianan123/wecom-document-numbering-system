import { createRouter, createWebHistory } from "vue-router";
import { authState, loadSession } from "./auth";
import AdminView from "./views/AdminView.vue";
import AdminComponentProjectsView from "./views/AdminComponentProjectsView.vue";
import LoginView from "./views/LoginView.vue";
import ProductComponentView from "./views/ProductComponentView.vue";
import UserCodeChoiceView from "./views/UserCodeChoiceView.vue";
import UserView from "./views/UserView.vue";
import ViewChoiceView from "./views/ViewChoiceView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/user" },
    { path: "/login", component: LoginView, meta: { public: true } },
    {
      path: "/choose-view",
      component: ViewChoiceView,
      meta: { role: "admin" }
    },
    { path: "/user", component: UserCodeChoiceView, meta: { role: "user" } },
    { path: "/user/files", component: UserView, meta: { role: "user" } },
    { path: "/user/components", component: ProductComponentView, meta: { role: "user" } },
    { path: "/admin", component: AdminView, meta: { role: "admin" } },
    { path: "/admin/components", component: AdminComponentProjectsView, meta: { role: "admin" } },
    { path: "/:pathMatch(.*)*", redirect: "/" }
  ]
});

router.beforeEach(async (to) => {
  if (to.meta.public) {
    await loadSession();
    if (authState.me) {
      return authState.me.user.role === "admin" ? "/choose-view" : "/user";
    }
    return true;
  }

  const me = await loadSession();
  if (!me) return { path: "/login", query: { next: to.fullPath } };
  if (to.meta.role === "admin" && me.user.role !== "admin") return "/user";
  return true;
});
