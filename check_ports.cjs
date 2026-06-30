const net = require('net');
const ports = [10000, 10001, 10002, 10010, 10080, 12000, 13000, 40000, 40001, 50000, 50001, 60000, 65000];

function checkPort(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => { server.close(); resolve(true); });
    server.listen(port);
  });
}

(async () => {
  for (const port of ports) {
    const available = await checkPort(port);
    console.log(port + ': ' + (available ? 'AVAILABLE' : 'IN USE'));
  }
})();