import { createApp } from "vue";
import {
  Button,
  Cell,
  CellGroup,
  Checkbox,
  Empty,
  Field,
  Loading,
  NavBar,
  NoticeBar,
  Tag
} from "vant";
import "vant/lib/index.css";
import App from "./App.vue";
import { router } from "./router";
import "./styles.css";

const app = createApp(App);
app.use(router);
app
  .use(Button)
  .use(Cell)
  .use(CellGroup)
  .use(Checkbox)
  .use(Empty)
  .use(Field)
  .use(Loading)
  .use(NavBar)
  .use(NoticeBar)
  .use(Tag);
app.mount("#app");
