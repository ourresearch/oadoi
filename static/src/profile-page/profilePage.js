angular.module('profilePage', [
    'ngRoute',
    'profileService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/u/:slug', {
      templateUrl: 'profile-page/profile.tpl.html',
      controller: 'profilePageCtrl',
      resolve: {
        profileResp: function($http, $route){
          var url = "/api/u/" + $route.current.params.slug
          return $http.get(url)
        }
      }
    })
  })



  .controller("profilePageCtrl", function($scope,
                                          $routeParams,
                                          profileResp){
    $scope.profile = profileResp.data
    console.log("here's the profile", $scope.profile)


  })




