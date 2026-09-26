let totalExpense = 0;

// =============================
// Split Expense
// =============================



// =============================
// Delete Expense
// =============================

function deleteRow(button){

    if(confirm("Delete this expense?")){

        let row=button.parentElement.parentElement;

        let amount=row.cells[3].innerHTML.replace("₹","");

        totalExpense -= parseFloat(amount);

        if(totalExpense<0){

            totalExpense=0;

        }

        document.getElementById("totalExpense").innerHTML="₹"+totalExpense.toFixed(2);

        row.remove();

    }

}