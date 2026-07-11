// Exercises for-loops, block scoping, and string concatenation.
fun greet(name) {
  return "hello, " + name;
}

print greet("quill");

var total = 0;
for (var i = 1; i <= 5; i = i + 1) {
  var squared = i * i;
  total = total + squared;
}
print total; // 55

{
  var total = "shadowed"; // inner block, does not affect outer `total`
  print total;
}
print total;
