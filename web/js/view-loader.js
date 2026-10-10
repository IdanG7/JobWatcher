// A slow response from a tab we left must never become the active controller.
export async function mountView(current, {key, name, root, render, onError}) {
  current.view?.cleanup?.();
  const token = Symbol(key);
  Object.assign(current, {key, name, view: null, token});
  try {
    const view = await render(root);
    if (current.token !== token) { view?.cleanup?.(); return false; }
    current.view = view || null;
    return true;
  } catch (error) {
    if (current.token === token) onError(error);
    return false;
  }
}
