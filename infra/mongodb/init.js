db.createUser({
  user: "work_order_user",
  pwd: "work_order_pass",
  roles: [{ role: "readWrite", db: "work_order_db" }]
});