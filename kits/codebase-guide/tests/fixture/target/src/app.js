// A tiny server, standing in for the codebase a guide explains.
function listen(port) {
  return { port };
}

async function saveWork(user, xml) {
  const row = { user, xml, at: Date.now() };
  return db.insert("submissions", row);
}
