// Mutual demonstration of while-loops and native functions.
fun factorial(n) {
  var result = 1;
  while (n > 1) {
    result = result * n;
    n = n - 1;
  }
  return result;
}

print factorial(10);
print clock() > 0;
