angular.module('settingsPage', [
    'ngRoute'
])



    .config(function($routeProvider) {
        $routeProvider.when('/settings', {
            templateUrl: 'settings-page/settings-page.tpl.html',
            controller: 'settingsPageCtrl',
            resolve: {
                isAuth: function($q, $auth){
                    if ($auth.isAuthenticated()){
                        return $q.resolve()
                    }
                    else {
                        return $q.reject("/settings only works if you're logged in.")
                    }
                }
            }
        })
    })



    .controller("settingsPageCtrl", function($scope, $auth, $location, $http){

        console.log("the settings page loaded")
        $scope.wantToDelete = false
        $scope.deleteProfile = function() {
            $http.delete("/api/me")
                .success(function(resp){
                    $auth.logout()
                    $location.path("/")
                    alert("Your profile has been deleted.")
                })
                .error(function(){
                    alert("Sorry, something went wrong!")
                })
        }

        $scope.refresh = function(){
            console.log("refreshing!")
            alert("Syncing your profile now! You should see results in a minute or two.")
        }

    })



